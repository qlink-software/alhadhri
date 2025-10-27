# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.osv.expression import AND, OR
from odoo.tools.misc import format_date


class LawyerDashboard(models.AbstractModel):
    _name = "qlk.lawyer.dashboard"
    _description = "Lawyer Dashboard Service"

    @api.model
    def _selection_label(self, record, field_name):
        field = record._fields.get(field_name)
        if not field or not getattr(field, "selection", None):
            return record[field_name]
        return dict(field.selection).get(record[field_name], record[field_name])

    @api.model
    def _combine_or(self, domains):
        result = []
        for domain in domains:
            if not domain:
                continue
            if not result:
                result = domain
            else:
                result = OR([result, domain])
        return result

    @api.model
    def _lawyer_domain(self, employee_ids, user_id, field_names, allow_all=False):
        if allow_all:
            return []
        domains = []
        if employee_ids:
            for field_name in field_names:
                domains.append([(field_name, "in", employee_ids)])
        if user_id:
            domains.append([("user_id", "=", user_id)])
        combined = self._combine_or(domains)
        return combined or [(0, "=", 1)]

    @api.model
    def _format_case(self, case, lang):
        return {
            "id": case.id,
            "name": case.name,
            "client": case.client_id.name or "",
            "state": {
                "value": case.state,
                "label": self._selection_label(case, "state") or "",
            },
            "status": {
                "value": case.status,
                "label": self._selection_label(case, "status") or "",
            },
            "next_hearing": case.next_hearing_date
            and format_date(self.env, case.next_hearing_date, lang_code=lang)
            or "",
            "url": {
                "res_model": "qlk.case",
                "res_id": case.id,
            },
        }

    @api.model
    def _format_hearing(self, hearing, lang):
        return {
            "id": hearing.id,
            "name": hearing.name,
            "case": hearing.case_id.name or "",
            "date": hearing.date
            and format_date(self.env, hearing.date, lang_code=lang)
            or "",
            "court": hearing.case_group.name or "",
            "url": {
                "res_model": "qlk.hearing",
                "res_id": hearing.id,
            },
        }

    @api.model
    def _format_consultation(self, consultation, lang):
        return {
            "id": consultation.id,
            "name": consultation.name,
            "client": consultation.client_id.name or "",
            "state": {
                "value": consultation.state,
                "label": self._selection_label(consultation, "state") or "",
            },
            "date": consultation.date
            and format_date(
                self.env, fields.Date.to_date(consultation.date), lang_code=lang
            )
            or "",
            "url": {
                "res_model": "qlk.consulting",
                "res_id": consultation.id,
            },
        }

    @api.model
    def _format_employee(self, employee):
        return {
            "id": employee.id,
            "name": employee.name,
            "job": employee.job_title or "",
            "work_email": employee.work_email or "",
            "work_phone": employee.work_phone or "",
            "leave_balance": getattr(employee, "remaining_leaves", 0.0),
            "url": {"res_model": "hr.employee", "res_id": employee.id} if employee.id else None,
        }

    @api.model
    def _format_leave(self, leave, lang):
        name = leave.name or (leave.holiday_status_id.display_name if leave.holiday_status_id else "")
        date_from_str = (
            format_date(self.env, fields.Date.to_date(leave.date_from), lang_code=lang)
            if leave.date_from
            else ""
        )
        date_to_str = (
            format_date(self.env, fields.Date.to_date(leave.date_to), lang_code=lang)
            if leave.date_to
            else ""
        )
        return {
            "id": leave.id,
            "name": name,
            "date_from": date_from_str,
            "date_to": date_to_str,
            "state": {
                "value": leave.state,
                "label": self._selection_label(leave, "state") or "",
            },
            "employee": leave.employee_id.name if leave.employee_id else "",
            "url": {"res_model": "hr.leave", "res_id": leave.id} if leave.id else None,
            "date_range": (date_from_str and date_to_str and f"{date_from_str} - {date_to_str}") or date_from_str or date_to_str,
        }

    @api.model
    def _get_hr_data(self, employee_ids, allow_all, lang):
        if "hr.employee" not in self.env:
            return {"available": False, "is_manager": allow_all}

        Employee = self.env["hr.employee"]
        employees = Employee.browse(employee_ids)
        if allow_all:
            employees = Employee.search([], order="name asc", limit=40)

        hr_data = {
            "available": bool(employees),
            "is_manager": allow_all,
            "overview": [],
            "upcoming_leaves": [],
            "pending_leave_requests": 0,
            "total_employees": 0,
            "employee": None,
        }

        if not employees:
            return hr_data

        Leave = self.env["hr.leave"] if "hr.leave" in self.env else False
        now_dt = fields.Datetime.now()

        if allow_all:
            hr_data["overview"] = [self._format_employee(emp) for emp in employees]
            hr_data["total_employees"] = Employee.search_count([])
            if Leave:
                pending_states = ["confirm", "validate1"]
                hr_data["pending_leave_requests"] = Leave.search_count(
                    [("state", "in", pending_states)]
                )
                upcoming = Leave.search(
                    [
                        ("state", "in", ["confirm", "validate1", "validate"]),
                        ("date_from", ">=", now_dt),
                    ],
                    order="date_from asc",
                    limit=10,
                )
                hr_data["upcoming_leaves"] = [self._format_leave(leave, lang) for leave in upcoming]
            return hr_data

        employee = employees[0]
        hr_data["employee"] = self._format_employee(employee)

        if Leave:
            upcoming = Leave.search(
                [
                    ("employee_id", "=", employee.id),
                    ("state", "in", ["confirm", "validate1", "validate"]),
                    ("date_from", ">=", now_dt),
                ],
                order="date_from asc",
                limit=5,
            )
            hr_data["upcoming_leaves"] = [self._format_leave(leave, lang) for leave in upcoming]
            hr_data["pending_leave_requests"] = Leave.search_count(
                [
                    ("employee_id", "=", employee.id),
                    ("state", "in", ["confirm", "validate1"]),
                ]
            )
        return hr_data

    @api.model
    def _format_complaint(self, complaint, lang):
        return {
            "id": complaint.id,
            "name": complaint.name,
            "client": complaint.client_id.name or "",
            "state": {
                "value": complaint.state,
                "label": self._selection_label(complaint, "state") or "",
            },
            "date": complaint.date
            and format_date(self.env, complaint.date, lang_code=lang)
            or "",
            "url": {
                "res_model": "qlk.police.complaint",
                "res_id": complaint.id,
            },
        }

    @api.model
    def _format_project(self, project):
        return {
            "id": project.id,
            "name": project.name,
            "code": project.code or "",
            "department": project.department,
            "stage": project.stage_id.name if project.stage_id else "",
            "client": project.client_id.name if project.client_id else "",
            "hours": round(project.task_hours_total or 0.0, 2),
            "url": {
                "res_model": "qlk.project",
                "res_id": project.id,
            },
        }

    @api.model
    def _get_action_metadata(self):
        refs = {
            "case": "qlk_law.act_open_qlk_case_view",
            "hearing": "qlk_law.act_open_qlk_hearing_view",
            "my_hearing": "qlk_law.act_open_qlk_my_hearing_view",
            "consultation": "qlk_law.act_open_qlk_consulting_view",
            "my_consultation": "qlk_law.act_open_qlk_my_consulting_view",
            "complaint": "qlk_law_police.act_open_qlk_police_complaint_view",
            "work": "qlk_law.act_open_qlk_work_view",
            "my_work": "qlk_law.act_open_qlk_my_work_view",
            "employees": "hr.open_view_employee_list",
            "leaves": "hr_holidays.hr_leave_action_my_department",
            "task": "qlk_task_management.action_qlk_task_all",
            "project": "qlk_project_management.action_qlk_project",
        }
        data = {}
        for key, xml_id in refs.items():
            action = self.env.ref(xml_id, raise_if_not_found=False)
            if action:
                data[key] = {"id": action.id}
        return data

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        lang = user.lang or "en_US"
        today = fields.Date.context_today(self)
        start_week = today - relativedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        employee_ids = user.employee_ids.ids
        is_manager = user.has_group("qlk_law.group_qlk_law_manager") or user.has_group(
            "base.group_system"
        )
        case_domain = self._lawyer_domain(
            employee_ids, user.id, ["employee_id", "employee_ids"], allow_all=is_manager
        )
        hearing_lawyer_domain = self._lawyer_domain(
            employee_ids, user.id, ["employee_id", "employee2_id", "employee_ids"], allow_all=is_manager
        )

        case_model = self.env["qlk.case"]
        cases = case_model.search(case_domain, order="next_hearing_date asc, write_date desc", limit=10)

        hearing_model = self.env["qlk.hearing"]
        hearings_week = hearing_model.search(
            AND([hearing_lawyer_domain, [("date", ">=", start_week), ("date", "<=", end_week)]]),
            order="date asc",
            limit=10,
        )
        hearings_today = hearing_model.search(
            AND([hearing_lawyer_domain, [("date", "=", today)]]),
            order="date asc",
        )

        consultation_items = []
        if "qlk.consulting" in self.env:
            consultation_model = self.env["qlk.consulting"]
            consultation_domain = self._lawyer_domain(
                employee_ids, user.id, ["employee_id"], allow_all=is_manager
            )
            consultation_items = consultation_model.search(
                consultation_domain,
                order="date desc",
                limit=10,
            )

        complaint_items = []
        if "qlk.police.complaint" in self.env:
            complaint_domain = self._lawyer_domain(
                employee_ids, user.id, ["employee_id", "employee_ids"], allow_all=is_manager
            )
            complaint_model = self.env["qlk.police.complaint"]
            complaint_items = complaint_model.search(
                complaint_domain,
                order="date desc",
                limit=10,
            )

        action_meta = self._get_action_metadata()

        project_items = []
        if "qlk.project" in self.env:
            project_domain = self._lawyer_domain(
                employee_ids,
                user.id,
                ["assigned_employee_ids"],
                allow_all=is_manager,
            )
            owner_domain = [("owner_id", "=", user.id)] if not is_manager else []
            if project_domain and owner_domain:
                project_domain = OR([project_domain, owner_domain])
            elif owner_domain:
                project_domain = owner_domain
            project_model = self.env["qlk.project"]
            project_items = project_model.search(project_domain, order="write_date desc", limit=10)

        work_domain = self._lawyer_domain(
            employee_ids, user.id, ["employee_id"], allow_all=is_manager
        )
        work_model = self.env["qlk.work"]
        work_count = work_model.search_count(work_domain)

        task_hours_total = 0.0
        task_count = 0
        task_action_meta = action_meta.get("task")
        if "qlk.task" in self.env:
            task_model = self.env["qlk.task"]
            task_domain = self._lawyer_domain(
                employee_ids, user.id, ["employee_id"], allow_all=is_manager
            )
            task_count = task_model.search_count(task_domain)
            if task_domain:
                approved_domain = AND([task_domain, [("approval_state", "=", "approved")]])
            else:
                approved_domain = [("approval_state", "=", "approved")]
            grouped = task_model.read_group(approved_domain, ["hours_spent"], [])
            if grouped:
                task_hours_total = grouped[0].get("hours_spent", 0.0) or 0.0

        timesheet_total = task_hours_total
        if not task_count:
            if "account.analytic.line" in self.env:
                ts_model = self.env["account.analytic.line"]
                if is_manager:
                    ts_domain = []
                elif employee_ids and "employee_id" in ts_model._fields:
                    ts_domain = [("employee_id", "in", employee_ids)]
                elif "user_id" in ts_model._fields:
                    ts_domain = [("user_id", "=", user.id)]
                else:
                    ts_domain = []

                if ts_domain is not None:
                    grouped = ts_model.read_group(ts_domain, ["unit_amount"], [])
                    if grouped:
                        timesheet_total = grouped[0].get("unit_amount", 0.0) or 0.0

        hr_data = self._get_hr_data(employee_ids, is_manager, lang)

        return {
            "user": {
                "name": user.name,
                "company": user.company_id.name if user.company_id else "",
            },
            "is_manager": is_manager,
            "palette": {
                "primary": "#0F5CA8",
                "accent": "#22B6C8",
                "muted": "#0D3E7A",
                "success": "#27AE60",
            },
            "cases": {
                "items": [self._format_case(case, lang) for case in cases],
                "count": len(cases),
                "action": action_meta.get("case"),
            },
            "hearings_week": {
                "items": [self._format_hearing(item, lang) for item in hearings_week],
                "count": len(hearings_week),
                "date_range": {
                    "start": format_date(self.env, start_week, lang_code=lang),
                    "end": format_date(self.env, end_week, lang_code=lang),
                    "start_raw": fields.Date.to_string(start_week),
                    "end_raw": fields.Date.to_string(end_week),
                },
                "action": action_meta.get("hearing") or action_meta.get("my_hearing"),
            },
            "hearings_today": {
                "items": [self._format_hearing(item, lang) for item in hearings_today],
                "count": len(hearings_today),
                "date": format_date(self.env, today, lang_code=lang),
                "date_raw": fields.Date.to_string(today),
                "action": action_meta.get("my_hearing") or action_meta.get("hearing"),
            },
            "consultations": {
                "items": [self._format_consultation(item, lang) for item in consultation_items],
                "count": len(consultation_items),
                "action": action_meta.get("my_consultation") or action_meta.get("consultation"),
            },
            "complaints": {
                "items": [self._format_complaint(item, lang) for item in complaint_items],
                "count": len(complaint_items),
                "action": action_meta.get("complaint"),
            },
            "projects": {
                "items": [self._format_project(item) for item in project_items],
                "count": len(project_items),
                "action": action_meta.get("project"),
            },
            "tasks": {
                "count": task_count or work_count,
                "hours": round(timesheet_total, 2),
                "action": task_action_meta or action_meta.get("my_work") or action_meta.get("work"),
            },
            "hr": {
                **hr_data,
                "actions": {
                    "employees": action_meta.get("employees"),
                    "leaves": action_meta.get("leaves"),
                },
            },
        }
