# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class LawyerDashboardExtension(models.AbstractModel):
    _inherit = "qlk.lawyer.dashboard"

    REQUIRED_HOURS_PER_DAY = 8.0

    @api.model
    def _get_current_employee(self):
        user = self.env.user
        employee = user.employee_id
        if not employee and user.employee_ids:
            employee = user.employee_ids[:1]
        if not employee and "hr.employee" in self.env:
            employee = self.env["hr.employee"].sudo().search(
                [("user_id", "=", user.id)],
                limit=1,
            )
        return employee

    @api.model
    def _sum_task_hours(self, domain):
        if "qlk.task" not in self.env:
            return 0.0
        task_model = self.env["qlk.task"].sudo()
        if "hours_spent" not in task_model._fields:
            return 0.0
        grouped_data = task_model.read_group(domain, ["hours_spent"], [])
        if not grouped_data:
            return 0.0
        total_hours = grouped_data[0].get("hours_spent", grouped_data[0].get("hours_spent_sum", 0.0))
        return round(total_hours or 0.0, 2)

    @api.model
    def _required_hours_between(self, date_from, date_to):
        if not date_from or not date_to or date_to < date_from:
            return 0.0
        total = 0.0
        current_date = date_from
        while current_date <= date_to:
            if current_date.weekday() < 5:
                total += self.REQUIRED_HOURS_PER_DAY
            current_date += timedelta(days=1)
        return round(total, 2)

    @api.model
    def _action_payload(self, xml_id):
        action = self.env.ref(xml_id, raise_if_not_found=False)
        return {"id": action.id} if action else False

    @api.model
    def _get_working_hours_payload(self, employee):
        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())
        required_week = self._required_hours_between(week_start, today)
        if not employee:
            return {
                "required_today": self.REQUIRED_HOURS_PER_DAY,
                "required_week": required_week,
                "completed_today": 0.0,
                "completed_week": 0.0,
                "remaining_today": self.REQUIRED_HOURS_PER_DAY,
                "daily_progress": 0.0,
                "weekly_progress": 0.0,
            }

        base_domain = [
            "|",
            "|",
            ("employee_id", "=", employee.id),
            ("assigned_user_id", "=", self.env.user.id),
            ("create_uid", "=", self.env.user.id),
        ]
        completed_today = self._sum_task_hours(base_domain + [("date_start", "=", today)])
        completed_week = self._sum_task_hours(
            base_domain + [("date_start", ">=", week_start), ("date_start", "<=", today)]
        )
        required_today = self.REQUIRED_HOURS_PER_DAY
        remaining_today = round(max(required_today - completed_today, 0.0), 2)
        daily_progress = round(min((completed_today / required_today) * 100.0, 100.0), 2) if required_today else 0.0
        weekly_progress = round(min((completed_week / required_week) * 100.0, 100.0), 2) if required_week else 0.0
        return {
            "required_today": round(required_today, 2),
            "required_week": round(required_week, 2),
            "completed_today": round(completed_today, 2),
            "completed_week": round(completed_week, 2),
            "remaining_today": remaining_today,
            "daily_progress": daily_progress,
            "weekly_progress": weekly_progress,
        }

    @api.model
    def _get_leave_requests_payload(self, employee):
        result = {"pending": 0, "approved": 0, "rejected": 0}
        if not employee or "hr.leave" not in self.env:
            return result
        leave_model = self.env["hr.leave"].sudo()
        result["pending"] = leave_model.search_count(
            [("employee_id", "=", employee.id), ("state", "in", ["confirm", "validate1"])]
        )
        result["approved"] = leave_model.search_count(
            [("employee_id", "=", employee.id), ("state", "=", "validate")]
        )
        result["rejected"] = leave_model.search_count(
            [("employee_id", "=", employee.id), ("state", "=", "refuse")]
        )
        return result

    @api.model
    def _get_warning_payload(self, employee, lang):
        result = {
            "active_count": 0,
            "latest_items": [],
            "alert": False,
        }
        if not employee or "hr.employee.warning" not in self.env:
            return result

        warning_model = self.env["hr.employee.warning"].sudo()
        domain = [("employee_id", "=", employee.id), ("state", "!=", "closed")]
        warnings = warning_model.search(domain, order="warning_date desc, id desc", limit=3)
        result["active_count"] = warning_model.search_count(domain)
        items = []
        for warning in warnings:
            items.append(
                {
                    "id": warning.id,
                    "reference": warning.name,
                    "message": warning.violation_description or warning.corrective_actions or warning.name,
                    "date": warning.warning_date and format_date(self.env, warning.warning_date, lang_code=lang) or "",
                    "state_label": self._selection_label(warning, "state") or "",
                    "punishment_label": self._selection_label(warning, "punishment") or "",
                    "url": {"res_model": "hr.employee.warning", "res_id": warning.id},
                }
            )
        result["latest_items"] = items
        result["alert"] = items[0] if items else False
        return result

    @api.model
    def _get_hr_forms_payload(self, employee):
        if not employee:
            return {"documents": 0, "resignations": 0}
        documents = 0
        resignations = 0
        if "qlk.employee.document" in self.env:
            documents = self.env["qlk.employee.document"].sudo().search_count(
                [("employee_id", "=", employee.id)]
            )
        if "hr.resignation.request" in self.env:
            resignations = self.env["hr.resignation.request"].sudo().search_count(
                [("employee_id", "=", employee.id)]
            )
        return {"documents": documents, "resignations": resignations}

    @api.model
    def _get_resignation_status_payload(self, employee, lang):
        payload = {
            "state": "none",
            "label": _("No Active Request"),
            "message": _("No resignation request has been submitted."),
            "countdown_days": 0,
            "effective_date": "",
            "rejection_reason": "",
            "manager": "",
            "current_request": False,
            "action": self._action_payload("qlk_management.action_hr_resignation_requests"),
            "domain": [("employee_id", "=", employee.id)] if employee else [],
        }
        if not employee or "hr.resignation.request" not in self.env:
            return payload

        request = self.env["hr.resignation.request"].sudo().search(
            [("employee_id", "=", employee.id)],
            order="create_date desc, id desc",
            limit=1,
        )
        if not request:
            return payload

        today = fields.Date.context_today(self)
        countdown_days = 0
        if request.effective_date:
            countdown_days = max((request.effective_date - today).days, 0)

        state_labels = {
            "draft": _("Draft"),
            "submitted": _("Pending Approval"),
            "approved": _("Approved"),
            "rejected": _("Rejected"),
        }
        payload.update(
            {
                "state": request.approval_state,
                "label": state_labels.get(request.approval_state, _("Unknown")),
                "manager": request.manager_id.name or "",
                "effective_date": request.effective_date and format_date(self.env, request.effective_date, lang_code=lang) or "",
                "countdown_days": countdown_days,
                "rejection_reason": request.rejection_reason or "",
                "current_request": {"res_model": "hr.resignation.request", "res_id": request.id},
            }
        )
        if request.approval_state == "submitted":
            payload["message"] = _("Pending Approval")
        elif request.approval_state == "approved":
            payload["message"] = _("Access ends in %s days") % countdown_days
        elif request.approval_state == "rejected":
            payload["message"] = request.rejection_reason or _("The resignation request was rejected.")
        else:
            payload["message"] = _("Draft resignation request not yet submitted.")
        return payload

    @api.model
    def _get_my_project_tasks_payload(self, lang):
        payload = {
            "items": [],
            "count": 0,
            "domain": [],
            "action": self._action_payload("project.action_view_task")
            or self._action_payload("project.action_view_all_task"),
        }
        if "project.task" not in self.env:
            return payload

        task_model = self.env["project.task"]
        if not task_model.check_access_rights("read", raise_exception=False):
            return payload

        user = self.env.user
        if "user_id" in task_model._fields:
            user_domain = [("user_id", "=", user.id)]
        elif "user_ids" in task_model._fields:
            user_domain = [("user_ids", "in", [user.id])]
        else:
            user_domain = [("create_uid", "=", user.id)]

        domain = list(user_domain)
        if "is_closed" in task_model._fields:
            domain.append(("is_closed", "=", False))
        elif "stage_id" in task_model._fields:
            stage_model_name = task_model._fields["stage_id"].comodel_name
            stage_model = self.env.get(stage_model_name)
            if stage_model and "fold" in stage_model._fields:
                domain.append(("stage_id.fold", "=", False))

        order_fields = []
        if "date_deadline" in task_model._fields:
            order_fields.append("date_deadline asc")
        order_fields.append("id desc")
        tasks = task_model.search(domain, order=", ".join(order_fields), limit=5)
        payload["count"] = task_model.search_count(domain)
        payload["domain"] = domain

        state_selection = dict(task_model._fields["state"].selection) if "state" in task_model._fields else {}
        items = []
        for task in tasks:
            deadline = ""
            if "date_deadline" in task._fields and task.date_deadline:
                deadline = format_date(self.env, task.date_deadline, lang_code=lang)
            status = task.stage_id.display_name if "stage_id" in task._fields and task.stage_id else ""
            if not status and "state" in task._fields:
                status = state_selection.get(task.state, task.state or "")
            items.append(
                {
                    "id": task.id,
                    "name": task.display_name,
                    "project": task.project_id.display_name if "project_id" in task._fields and task.project_id else "",
                    "deadline": deadline,
                    "status": status or "",
                    "url": {"res_model": "project.task", "res_id": task.id},
                }
            )
        payload["items"] = items
        return payload

    @api.model
    def _active_case_domain(self):
        case_model = self.env["qlk.case"]
        return [("active", "=", True)] if "active" in case_model._fields else []

    @api.model
    def _synchronize_case_card(self, data):
        active_domain = self._active_case_domain()
        if not active_domain:
            return
        for card in data.get("kpi_cards") or []:
            if card.get("key") != "cases":
                continue
            case_domain = self._merge_domain(card.get("domain") or [], active_domain)
            card["domain"] = case_domain
            card["count"] = self.env["qlk.case"].search_count(case_domain)
            break

    @api.model
    def get_dashboard_data(self):
        data = super().get_dashboard_data()
        self._synchronize_case_card(data)
        user = self.env.user
        employee = self._get_current_employee()
        lang = user.lang or self.env.context.get("lang")

        working_hours = self._get_working_hours_payload(employee)
        leave_requests = self._get_leave_requests_payload(employee)
        warnings = self._get_warning_payload(employee, lang)
        hr_forms = self._get_hr_forms_payload(employee)
        resignation_status = self._get_resignation_status_payload(employee, lang)
        my_project_tasks = self._get_my_project_tasks_payload(lang)

        labels = data.get("labels") or {}
        labels.update(
            {
                "working_hours_title": _("Working Hours"),
                "working_hours_subtitle": _("Employee-specific hours tracked from task entries by task date."),
                "required_hours_title": _("Required Hours"),
                "today_completed_title": _("Completed Today"),
                "week_completed_title": _("Completed This Week"),
                "remaining_hours_title": _("Remaining Hours"),
                "daily_progress_title": _("Daily Progress"),
                "weekly_progress_title": _("Weekly Progress"),
                "hr_requests_alerts_title": _("HR Requests & Alerts"),
                "hr_requests_alerts_subtitle": _("Leave requests, warnings, and employee HR forms."),
                "pending_leave_title": _("Pending Leave"),
                "approved_leave_title": _("Approved Leave"),
                "rejected_leave_title": _("Rejected Leave"),
                "active_warnings_title": _("Active Warnings"),
                "hr_forms_title": _("HR Forms"),
                "resignations_title": _("Resignations"),
                "warning_alert_title": _("Active HR Warning"),
                "warning_alert_subtitle": _("Immediate attention is required for the latest employee warning."),
                "warning_message_title": _("Warning Message"),
                "warning_date_title": _("Warning Date"),
                "resignation_status_title": _("Resignation Status"),
                "resignation_status_subtitle": _("Track submission, approval, and access end date."),
                "view_leaves": _("View Leaves"),
                "view_warnings": _("View Warnings"),
                "view_documents": _("View Documents"),
                "view_resignations": _("View Resignations"),
                "view_request": _("Open Request"),
                "view_warning": _("Open Warning"),
                "hours_unit": _("hours"),
                "days_unit": _("days"),
                "manager_title": _("Manager"),
                "effective_date_title": _("Effective Date"),
                "latest_warnings_title": _("Latest 3 Warnings"),
                "no_warning_data": _("No active warnings for this employee."),
                "my_tasks_title": _("مهامي"),
                "my_tasks_subtitle": _("المهام المفتوحة المسندة إليك في المشاريع."),
                "task_name_title": _("Task Name"),
                "task_project_title": _("Project"),
                "task_deadline_title": _("Deadline"),
                "task_status_title": _("Status"),
                "view_all_tasks": _("View All"),
                "no_project_tasks": _("لا توجد مهام مفتوحة حالياً."),
            }
        )
        data["labels"] = labels
        data["working_hours"] = working_hours
        data["my_project_tasks"] = my_project_tasks
        leave_base_domain = [("employee_id", "=", employee.id)] if employee else []
        warning_base_domain = [("employee_id", "=", employee.id)] if employee else []
        resignation_base_domain = [("employee_id", "=", employee.id)] if employee else []
        data["hr_requests_alerts"] = {
            "leave_requests": leave_requests,
            "warnings": warnings,
            "forms": hr_forms,
            "actions": {
                "leaves": self._action_payload("hr_holidays.hr_leave_action_my")
                or self._action_payload("hr_holidays.hr_holidays_dashboard_action"),
                "warnings": self._action_payload("hr_qatar.hr_employee_warning_action"),
                "documents": self._action_payload("qlk_management.action_employee_documents"),
                "resignations": self._action_payload("qlk_management.action_hr_resignation_requests"),
            },
            "domains": {
                "leaves": leave_base_domain,
                "pending_leaves": leave_base_domain + [("state", "in", ["confirm", "validate1"])],
                "approved_leaves": leave_base_domain + [("state", "=", "validate")],
                "rejected_leaves": leave_base_domain + [("state", "=", "refuse")],
                "warnings": warning_base_domain + [("state", "!=", "closed")],
                "documents": [("employee_id", "=", employee.id)] if employee else [],
                "resignations": resignation_base_domain,
            },
        }
        data["warning_alert"] = warnings.get("alert")
        data["resignation_status"] = resignation_status
        return data
