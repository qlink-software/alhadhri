# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


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
        allow_all = user.has_group("qlk_law.group_qlk_law_manager") or user.has_group("base.group_system")
        employee_ids = user.employee_ids.ids

        try:
            months = int(months)
        except (TypeError, ValueError):
            months = 6
        months = max(1, min(months, 24))

        def project_domain():
            if allow_all:
                return []
            domain = [("owner_id", "=", user.id)]
            if employee_ids:
                domain = ["|", ("assigned_employee_ids", "in", employee_ids)] + domain
            return domain

        totals = {
            "cases": self._summaries("qlk.case"),
            "hearings": self._summaries("qlk.hearing"),
            "consultations": self._summaries("qlk.consulting") if "qlk.consulting" in self.env else 0,
            "complaints": self._summaries("qlk.police.complaint") if "qlk.police.complaint" in self.env else 0,
            "projects": self._summaries("qlk.project", project_domain()),
        }

        task_domain = [("project_id", "!=", False)]
        if not allow_all:
            if employee_ids:
                task_domain.append(("employee_id", "in", employee_ids))
            else:
                task_domain.append(("assigned_user_id", "=", user.id))

        approved_task_domain = task_domain + [("approval_state", "=", "approved")]

        task_hours_group = self.env["qlk.task"].read_group(approved_task_domain, ["hours_spent"], [])
        totals["task_hours"] = task_hours_group[0].get("hours_spent", 0.0) if task_hours_group else 0.0

        def safe_aggregate(model, domain=None, date_field="date", value_field="id", value_type="count", action=None):
            if model not in self.env:
                return []
            return self._aggregate_monthly(model, domain, date_field, value_field, value_type, months=months, action=action)

        case_status = []
        if "qlk.case" in self.env:
            selection = dict(self.env["qlk.case"]._fields["status"].selection)
            grouped = self.env["qlk.case"].read_group([], ["status"], ["status"])
            for entry in grouped:
                status = entry.get("status")
                if not status:
                    continue
                case_status.append(
                    {
                        "label": selection.get(status, status),
                        "value": entry.get("status_count", 0),
                        "domain": [["status", "=", status]],
                        "action": "cases",
                    }
                )

        hearing_stage = []
        if "qlk.hearing" in self.env:
            selection = dict(self.env["qlk.hearing"]._fields["state"].selection)
            grouped = self.env["qlk.hearing"].read_group([], ["state"], ["state"])
            for entry in grouped:
                state = entry.get("state")
                if not state:
                    continue
                hearing_stage.append(
                    {
                        "label": selection.get(state, state),
                        "value": entry.get("state_count", 0),
                        "domain": [["state", "=", state]],
                        "action": "hearings",
                    }
                )

        project_progress = []
        if "qlk.project" in self.env:
            grouped = self.env["qlk.project"].read_group(project_domain(), ["stage_id"], ["stage_id"])
            for entry in grouped:
                stage_ref = entry.get("stage_id")
                if not stage_ref:
                    continue
                project_progress.append(
                    {
                        "label": stage_ref[1],
                        "value": entry.get("stage_id_count", 0),
                        "domain": [["stage_id", "=", stage_ref[0]]],
                        "action": "projects",
                    }
                )

        task_department = []
        if "qlk.task" in self.env:
            selection = dict(self.env["qlk.task"]._fields["department"].selection)
            grouped = self.env["qlk.task"].read_group(task_domain, ["department"], ["department"])
            for entry in grouped:
                dept = entry.get("department")
                if not dept:
                    continue
                task_department.append(
                    {
                        "label": selection.get(dept, dept),
                        "value": entry.get("department_count", 0),
                        "domain": [["department", "=", dept], ["project_id", "!=", False]],
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
                "cases": safe_aggregate("qlk.case", date_field="date", action="cases"),
                "hearings": safe_aggregate("qlk.hearing", date_field="date", action="hearings"),
                "consultations": safe_aggregate("qlk.consulting", date_field="date", action="consultations") if "qlk.consulting" in self.env else [],
                "complaints": safe_aggregate("qlk.police.complaint", date_field="date", action="complaints") if "qlk.police.complaint" in self.env else [],
                "projects": safe_aggregate("qlk.project", project_domain(), date_field="create_date", action="projects"),
                "task_hours": safe_aggregate("qlk.task", approved_task_domain, date_field="date_start", value_field="hours_spent", value_type="sum", action="tasks"),
                "case_status": case_status,
                "hearing_stage": hearing_stage,
                "project_progress": project_progress,
                "task_department": task_department,
            },
            "actions": {
                "cases": self._action_ref("qlk_law.act_open_qlk_case_view"),
                "hearings": self._action_ref("qlk_law.act_open_qlk_hearing_view"),
                "consultations": self._action_ref("qlk_law.act_open_qlk_consulting_view"),
                "complaints": self._action_ref("qlk_law_police.act_open_qlk_police_complaint_view"),
                "projects": self._action_ref("qlk_project_management.action_qlk_project"),
                "tasks": self._action_ref("qlk_project_management.action_qlk_project_tasks"),
            },
        }
        return data

    def _action_ref(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if action:
            return {"id": action.id}
        return None
