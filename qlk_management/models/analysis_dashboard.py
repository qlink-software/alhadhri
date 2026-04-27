# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.osv.expression import OR


class QlkAnalysisDashboard(models.AbstractModel):
    _name = "qlk.analysis.dashboard"
    _description = "Analytics Dashboard Service"

    def _month_ranges(self, months=6):
        today = fields.Date.context_today(self)
        start_month = today.replace(day=1) - relativedelta(months=months - 1)
        ranges = []
        for i in range(months):
            current = start_month + relativedelta(months=i)
            start = current
            end = current + relativedelta(months=1, days=-1)
            label = current.strftime("%Y-%m")
            ranges.append((label, fields.Date.to_string(start), fields.Date.to_string(end)))
        return ranges

    def _normalize_domain(self, domain):
        normalized = []
        for term in domain:
            if isinstance(term, (list, tuple)):
                normalized.append(list(term))
            else:
                normalized.append(term)
        return normalized

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني دومين مرتبط بالمستخدم الحالي لضمان عرض إحصائياته الشخصية.
    # ------------------------------------------------------------------------------
    def _scoped_domain(self, model_name, user, employee_ids, allow_all, base_domain=None):
        domain = list(base_domain or [])
        if allow_all or model_name not in self.env:
            return domain

        Model = self.env[model_name]
        user_scopes = []
        if "owner_id" in Model._fields:
            user_scopes.append([("owner_id", "=", user.id)])
        if "user_id" in Model._fields:
            user_scopes.append([("user_id", "=", user.id)])
        if "assigned_user_id" in Model._fields:
            user_scopes.append([("assigned_user_id", "=", user.id)])
        if "reviewer_id" in Model._fields:
            user_scopes.append([("reviewer_id", "=", user.id)])
        if employee_ids and "employee_id" in Model._fields:
            user_scopes.append([("employee_id", "in", employee_ids)])
        if employee_ids and "assigned_employee_ids" in Model._fields:
            user_scopes.append([("assigned_employee_ids", "in", employee_ids)])
        # create_uid متوفر افتراضيًا في أغلب الموديلات ويعمل كحل احتياطي.
        if "create_uid" in Model._fields:
            user_scopes.append([("create_uid", "=", user.id)])

        if user_scopes:
            domain += OR(user_scopes)
        return domain

    def _aggregate_monthly(self, model_name, domain=None, date_field="date", value_field="id", value_type="count", months=6, action=None):
        if model_name not in self.env:
            return []

        Model = self.env[model_name]
        domain = domain or []
        ranges = self._month_ranges(months=months)
        results = []
        for label, date_from, date_to in ranges:
            local_domain = list(domain)
            local_domain += [
                (date_field, ">=", date_from),
                (date_field, "<=", date_to),
            ]
            if value_type == "count":
                value = Model.search_count(local_domain)
            else:
                read = Model.read_group(local_domain, [value_field], [])
                value = read[0].get(value_field, 0.0) if read else 0.0
            results.append(
                {
                    "label": label,
                    "value": value,
                    "domain": self._normalize_domain(local_domain),
                    "action": action,
                }
            )
        return results

    def _summaries(self, model_name, domain=None):
        if model_name not in self.env:
            return 0
        return self.env[model_name].search_count(domain or [])

    @api.model
    def get_dashboard_data(self, months=6):
        user = self.env.user
        employee_ids = user.employee_ids.ids
        # هذا المتغير يفعّل عرض شامل للمديرين فقط، ويقيّد بقية الموظفين ببياناتهم.
        allow_all = user._qlk_can_view_all_dashboards()

        try:
            months = int(months)
        except (TypeError, ValueError):
            months = 6
        months = max(1, min(months, 24))

        def scoped_domain(model_name, base_domain=None):
            return self._scoped_domain(model_name, user, employee_ids, allow_all, base_domain)

        task_domain = scoped_domain("qlk.task", [])
        approved_task_domain = task_domain + [("approval_state", "=", "approved")]

        totals = {
            "cases": self._summaries("qlk.case", scoped_domain("qlk.case")),
            "hearings": self._summaries("qlk.hearing", scoped_domain("qlk.hearing")),
            "consultations": self._summaries("qlk.consulting", scoped_domain("qlk.consulting")) if "qlk.consulting" in self.env else 0,
            "complaints": self._summaries("qlk.police.complaint", scoped_domain("qlk.police.complaint")) if "qlk.police.complaint" in self.env else 0,
            "engagements": self._summaries("bd.engagement.letter", scoped_domain("bd.engagement.letter")),
        }

        task_hours_group = self.env["qlk.task"].read_group(approved_task_domain, ["hours_spent"], [])
        totals["task_hours"] = task_hours_group[0].get("hours_spent", 0.0) if task_hours_group else 0.0

        def safe_aggregate(model, domain=None, date_field="date", value_field="id", value_type="count", action=None):
            if model not in self.env:
                return []
            return self._aggregate_monthly(model, domain, date_field, value_field, value_type, months=months, action=action)

        case_status = []
        if "qlk.case" in self.env:
            case_model = self.env["qlk.case"]
            case_base_domain = scoped_domain("qlk.case")
            selection = dict(case_model._fields["status"].selection)
            grouped = case_model.read_group(case_base_domain, ["status"], ["status"])
            for entry in grouped:
                status = entry.get("status")
                if not status:
                    continue
                local_domain = case_base_domain + [("status", "=", status)]
                case_status.append(
                    {
                        "label": selection.get(status, status),
                        "value": entry.get("status_count", 0),
                        "domain": self._normalize_domain(local_domain),
                        "action": "cases",
                    }
                )

        hearing_stage = []
        if "qlk.hearing" in self.env:
            hearing_model = self.env["qlk.hearing"]
            hearing_base_domain = scoped_domain("qlk.hearing")
            selection = dict(hearing_model._fields["state"].selection)
            grouped = hearing_model.read_group(hearing_base_domain, ["state"], ["state"])
            for entry in grouped:
                state = entry.get("state")
                if not state:
                    continue
                local_domain = hearing_base_domain + [("state", "=", state)]
                hearing_stage.append(
                    {
                        "label": selection.get(state, state),
                        "value": entry.get("state_count", 0),
                        "domain": self._normalize_domain(local_domain),
                        "action": "hearings",
                    }
                )

        task_department = []
        if "qlk.task" in self.env:
            task_model = self.env["qlk.task"]
            selection = dict(task_model._fields["department"].selection)
            grouped = task_model.read_group(task_domain, ["department"], ["department"])
            for entry in grouped:
                dept = entry.get("department")
                if not dept:
                    continue
                local_domain = task_domain + [("department", "=", dept)]
                task_department.append(
                    {
                        "label": selection.get(dept, dept),
                        "value": entry.get("department_count", 0),
                        "domain": self._normalize_domain(local_domain),
                        "action": "tasks",
                    }
                )

        data = {
            "palette": {
                "primary": "#0F5CA8",
                "accent": "#22B6C8",
                "muted": "#0D3E7A",
                "success": "#27AE60",
            },
            "totals": totals,
            "series": {
                "cases": safe_aggregate("qlk.case", scoped_domain("qlk.case"), date_field="date", action="cases"),
                "hearings": safe_aggregate("qlk.hearing", scoped_domain("qlk.hearing"), date_field="date", action="hearings"),
                "consultations": safe_aggregate("qlk.consulting", scoped_domain("qlk.consulting"), date_field="date", action="consultations") if "qlk.consulting" in self.env else [],
                "complaints": safe_aggregate("qlk.police.complaint", scoped_domain("qlk.police.complaint"), date_field="date", action="complaints") if "qlk.police.complaint" in self.env else [],
                "engagements": safe_aggregate("bd.engagement.letter", scoped_domain("bd.engagement.letter"), date_field="date", action="engagements"),
                "task_hours": safe_aggregate("qlk.task", approved_task_domain, date_field="date_start", value_field="hours_spent", value_type="sum", action="tasks"),
                "case_status": case_status,
                "hearing_stage": hearing_stage,
                "task_department": task_department,
            },
            "actions": {
                "cases": self._action_ref("qlk_law.act_open_qlk_case_view"),
                "hearings": self._action_ref("qlk_law.act_open_qlk_hearing_view"),
                "consultations": self._action_ref("qlk_law.act_open_qlk_consulting_view"),
                "complaints": self._action_ref("qlk_law_police.act_open_qlk_police_complaint_view"),
                "engagements": self._action_ref("qlk_management.action_bd_engagement_letter"),
                "tasks": self._action_ref("qlk_task_management.action_qlk_task_all"),
            },
        }
        return data

    def _action_ref(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if action:
            return {"id": action.id}
        return None
