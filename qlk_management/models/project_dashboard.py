# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.osv.expression import OR


class QlkProjectDashboard(models.AbstractModel):
    _name = "qlk.project.dashboard"
    _description = "Project Dashboard Service"

    REQUIRED_HOURS_PER_DAY = 8.0

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني دومين المشاريع حسب المستخدم الحالي لضمان عرض بياناته فقط.
    # ------------------------------------------------------------------------------
    def _project_domain(self, employee_ids, user, allow_all):
        if allow_all:
            return []
        domain = []
        if employee_ids:
            domain.append(("assigned_employee_ids", "in", employee_ids))
        domain.append(("owner_id", "=", user.id))
        if len(domain) == 1:
            return domain
        return OR([domain[:-1], [domain[-1]]])

    # ------------------------------------------------------------------------------
    # هذه الدالة تحسب الساعات المطلوبة بين تاريخين (8 ساعات لكل يوم عمل).
    # ------------------------------------------------------------------------------
    def _required_hours_between(self, date_from, date_to):
        if not date_from or not date_to or date_to < date_from:
            return 0.0
        days_count = (date_to - date_from).days + 1
        total = 0.0
        for offset in range(days_count):
            current_day = date_from + timedelta(days=offset)
            if current_day.weekday() < 5:
                total += self.REQUIRED_HOURS_PER_DAY
        return total

    # ------------------------------------------------------------------------------
    # هذه الدالة ترجع map بساعات الحضور لكل موظف من hr.attendance.
    # ------------------------------------------------------------------------------
    def _attendance_hours_map(self, employee_ids, datetime_from, datetime_to):
        if not employee_ids or "hr.attendance" not in self.env:
            return {}
        grouped = self.env["hr.attendance"].read_group(
            [
                ("employee_id", "in", employee_ids),
                ("check_in", ">=", datetime_from),
                ("check_in", "<=", datetime_to),
            ],
            ["employee_id", "worked_hours"],
            ["employee_id"],
            lazy=False,
        )
        return {
            entry["employee_id"][0]: float(entry.get("worked_hours") or 0.0)
            for entry in grouped
            if entry.get("employee_id")
        }

    # ------------------------------------------------------------------------------
    # هذه الدالة تحسب رصيد الإجازات (مخصص/مستخدم/متبقي) لكل موظف.
    # ------------------------------------------------------------------------------
    def _leave_balance_map(self, employee_ids):
        balances = {
            employee_id: {"allocated": 0.0, "used": 0.0, "remaining": 0.0}
            for employee_id in employee_ids
        }
        if not employee_ids:
            return balances
        if "hr.leave" not in self.env or "hr.leave.allocation" not in self.env:
            return balances

        allocation_model = self.env["hr.leave.allocation"]
        leave_model = self.env["hr.leave"]
        leave_type_model = self.env["hr.leave.type"] if "hr.leave.type" in self.env else self.env["ir.model"]

        alloc_qty_field = "number_of_days" if "number_of_days" in allocation_model._fields else "number_of_days_display"
        leave_qty_field = "number_of_days" if "number_of_days" in leave_model._fields else "number_of_days_display"

        allocation_domain = [
            ("employee_id", "in", employee_ids),
            ("state", "=", "validate"),
        ]
        leave_domain = [
            ("employee_id", "in", employee_ids),
            ("state", "=", "validate"),
        ]
        if "holiday_type" in leave_model._fields:
            leave_domain.append(("holiday_type", "=", "employee"))
        if "holiday_status_id" in leave_model._fields and hasattr(leave_type_model, "_fields"):
            if "requires_allocation" in leave_type_model._fields:
                leave_domain.append(("holiday_status_id.requires_allocation", "=", True))
            if "unpaid" in leave_type_model._fields:
                leave_domain.append(("holiday_status_id.unpaid", "=", False))

        allocation_groups = allocation_model.read_group(
            allocation_domain,
            ["employee_id", alloc_qty_field],
            ["employee_id"],
            lazy=False,
        )
        for row in allocation_groups:
            if not row.get("employee_id"):
                continue
            employee_id = row["employee_id"][0]
            balances.setdefault(employee_id, {"allocated": 0.0, "used": 0.0, "remaining": 0.0})
            balances[employee_id]["allocated"] = float(row.get(alloc_qty_field) or 0.0)

        leave_groups = leave_model.read_group(
            leave_domain,
            ["employee_id", leave_qty_field],
            ["employee_id"],
            lazy=False,
        )
        for row in leave_groups:
            if not row.get("employee_id"):
                continue
            employee_id = row["employee_id"][0]
            balances.setdefault(employee_id, {"allocated": 0.0, "used": 0.0, "remaining": 0.0})
            balances[employee_id]["used"] = float(row.get(leave_qty_field) or 0.0)

        for employee_id, values in balances.items():
            values["remaining"] = round(values["allocated"] - values["used"], 2)
        return balances

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني بيانات قسم HR داخل داشبورد الموظف.
    # ------------------------------------------------------------------------------
    def _build_hr_dashboard_payload(self, user, employee_ids, allow_all):
        employee_model = self.env["hr.employee"]
        if allow_all:
            scoped_employees = employee_model.search([("active", "=", True)], order="name", limit=200)
        else:
            scoped_employees = user.employee_ids.filtered(lambda employee: employee.active)

        if not scoped_employees:
            return {
                "employees": [],
                "warnings": [],
                "requests": {
                    "my_leaves": 0,
                    "pending_approvals": 0,
                    "documents_total": 0,
                    "documents_waiting_approval": 0,
                },
                "leave_totals": {"allocated": 0.0, "used": 0.0, "remaining": 0.0},
                "actions": {},
            }

        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())

        day_start = datetime.combine(today, time.min)
        day_end = datetime.combine(today, time.max)
        week_start_dt = datetime.combine(week_start, time.min)
        week_end_dt = datetime.combine(today, time.max)

        scoped_employee_ids = scoped_employees.ids
        daily_hours_map = self._attendance_hours_map(scoped_employee_ids, day_start, day_end)
        weekly_hours_map = self._attendance_hours_map(scoped_employee_ids, week_start_dt, week_end_dt)
        leave_balance_map = self._leave_balance_map(scoped_employee_ids)

        required_daily = self.REQUIRED_HOURS_PER_DAY
        required_weekly = self._required_hours_between(week_start, today)

        warnings = []
        employees_payload = []
        for employee in scoped_employees:
            daily_hours = round(float(daily_hours_map.get(employee.id, 0.0)), 2)
            weekly_hours = round(float(weekly_hours_map.get(employee.id, 0.0)), 2)
            leave_balance = leave_balance_map.get(
                employee.id,
                {"allocated": 0.0, "used": 0.0, "remaining": 0.0},
            )
            missing_daily = max(required_daily - daily_hours, 0.0)
            missing_weekly = max(required_weekly - weekly_hours, 0.0)

            if missing_daily > 0:
                warnings.append(
                    _("%s has daily hours below target by %.2f hours.")
                    % (employee.name, missing_daily)
                )
            if missing_weekly > 0:
                warnings.append(
                    _("%s is missing %.2f weekly hours.")
                    % (employee.name, missing_weekly)
                )

            employees_payload.append(
                {
                    "id": employee.id,
                    "name": employee.name,
                    "daily_hours": daily_hours,
                    "weekly_hours": weekly_hours,
                    "required_daily": required_daily,
                    "required_weekly": round(required_weekly, 2),
                    "missing_daily": round(missing_daily, 2),
                    "missing_weekly": round(missing_weekly, 2),
                    "leave": {
                        "allocated": round(float(leave_balance.get("allocated", 0.0)), 2),
                        "used": round(float(leave_balance.get("used", 0.0)), 2),
                        "remaining": round(float(leave_balance.get("remaining", 0.0)), 2),
                    },
                }
            )

        leave_totals = {
            "allocated": round(sum(item["leave"]["allocated"] for item in employees_payload), 2),
            "used": round(sum(item["leave"]["used"] for item in employees_payload), 2),
            "remaining": round(sum(item["leave"]["remaining"] for item in employees_payload), 2),
        }

        leave_model = self.env.get("hr.leave")
        my_leave_requests = 0
        pending_approvals = 0
        if leave_model and employee_ids:
            my_leave_requests = leave_model.search_count(
                [
                    ("employee_id", "in", employee_ids),
                    ("state", "in", ["confirm", "validate1"]),
                ]
            )

            approval_domain = [("state", "in", ["confirm", "validate1"])]
            approval_scopes = []
            if "first_approver_id" in leave_model._fields:
                approval_scopes.append([("first_approver_id", "=", user.id)])
            if "second_approver_id" in leave_model._fields:
                approval_scopes.append([("second_approver_id", "=", user.id)])
            if approval_scopes:
                approval_domain += OR(approval_scopes)
                pending_approvals = leave_model.search_count(approval_domain)
            elif allow_all:
                pending_approvals = leave_model.search_count(approval_domain)
            else:
                pending_approvals = my_leave_requests

        document_model = self.env.get("qlk.employee.document")
        documents_total = 0
        documents_waiting_approval = 0
        if document_model and employee_ids:
            documents_total = document_model.search_count([("employee_id", "in", employee_ids)])
            if user.has_group("qlk_management.group_hr_nda_manager"):
                documents_waiting_approval = document_model.search_count([("status", "=", "waiting_approval")])
            else:
                documents_waiting_approval = document_model.search_count(
                    [
                        ("requested_by", "=", user.id),
                        ("status", "=", "waiting_approval"),
                    ]
                )

        actions = {}
        leave_action = self.env.ref("hr_holidays.hr_leave_action_my", raise_if_not_found=False)
        if not leave_action:
            leave_action = self.env.ref("hr_holidays.hr_holidays_dashboard_action", raise_if_not_found=False)
        if leave_action:
            actions["leaves"] = {"id": leave_action.id}

        attendance_action = self.env.ref("hr_attendance.hr_attendance_action", raise_if_not_found=False)
        if attendance_action:
            actions["attendance"] = {"id": attendance_action.id}

        documents_action = self.env.ref("qlk_management.action_employee_documents", raise_if_not_found=False)
        if documents_action:
            actions["documents"] = {"id": documents_action.id}

        return {
            "employees": employees_payload,
            "warnings": warnings[:20],
            "requests": {
                "my_leaves": my_leave_requests,
                "pending_approvals": pending_approvals,
                "documents_total": documents_total,
                "documents_waiting_approval": documents_waiting_approval,
            },
            "leave_totals": leave_totals,
            "actions": actions,
        }

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        employee_ids = user.employee_ids.ids
        # هذا المتغير يحدد هل يرى المستخدم كل البيانات أم بياناته الشخصية فقط.
        allow_all = user._qlk_can_view_all_dashboards()

        project_model = self.env["qlk.project"]
        project_domain = self._project_domain(employee_ids, user, allow_all)
        projects = project_model.search(project_domain, order="write_date desc", limit=10)
        total_projects = project_model.search_count(project_domain)

        case_condition = [
            "|",
            "|",
            ("case_id", "!=", False),
            ("corporate_case_id", "!=", False),
            ("arbitration_case_id", "!=", False),
        ]
        if project_domain:
            projects_with_case = project_model.search_count(OR([project_domain, case_condition]))
        else:
            projects_with_case = project_model.search_count(case_condition)

        department_labels = {
            "litigation": _("Litigation"),
            "corporate": _("Corporate"),
            "arbitration": _("Arbitration"),
        }

        department_stats = []
        dept_read = project_model.read_group(project_domain, ["department"], ["department"])
        dept_map = {entry["department"]: entry["department_count"] for entry in dept_read if entry.get("department")}
        for key, label in department_labels.items():
            department_stats.append(
                {
                    "key": key,
                    "label": label,
                    "count": dept_map.get(key, 0),
                }
            )

        project_ids = projects.ids if projects else []
        task_model = self.env["qlk.task"]
        task_domain = [("project_id", "!=", False)]
        if not allow_all:
            # هذا الدومين يربط الإحصائيات بمهام المستخدم/الموظف الحالي فقط.
            task_scope_domains = []
            if employee_ids and "employee_id" in task_model._fields:
                task_scope_domains.append([("employee_id", "in", employee_ids)])
            if "assigned_user_id" in task_model._fields:
                task_scope_domains.append([("assigned_user_id", "=", user.id)])
            task_scope_domains.append([("create_uid", "=", user.id)])
            task_domain += OR(task_scope_domains)

        total_tasks = task_model.search_count(task_domain)
        waiting_tasks = task_model.search_count(task_domain + [("approval_state", "=", "waiting")])
        approved_tasks = task_model.search_count(task_domain + [("approval_state", "=", "approved")])
        rejected_tasks = task_model.search_count(task_domain + [("approval_state", "=", "rejected")])

        hours_total = 0.0
        hours_group = task_model.read_group(task_domain + [("approval_state", "=", "approved")], ["hours_spent"], [])
        if hours_group:
            hours_total = hours_group[0].get("hours_spent", 0.0) or 0.0

        task_map = defaultdict(lambda: {"count": 0, "hours": 0.0})
        if project_ids:
            grouped = task_model.read_group(
                task_domain + [("project_id", "in", project_ids)],
                ["hours_spent", "project_id"],
                ["project_id"],
            )
            for entry in grouped:
                project_ref = entry.get("project_id")
                if not project_ref:
                    continue
                project_id = project_ref[0]
                task_map[project_id]["count"] = entry.get("project_id_count", 0)
                task_map[project_id]["hours"] = entry.get("hours_spent", 0.0) or 0.0

        project_cards = []
        for project in projects:
            project_cards.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "code": project.code or "",
                    "client": project.client_id.name if project.client_id else "",
                    "department": department_labels.get(project.department, project.department),
                    "case": project.related_case_display or "",
                    "has_case": bool(project.case_id or project.corporate_case_id or project.arbitration_case_id),
                    "tasks": task_map[project.id]["count"],
                    "hours": round(task_map[project.id]["hours"], 2),
                    "url": {"res_model": "qlk.project", "res_id": project.id},
                }
            )

        actions = {
            "projects": self.env.ref("qlk_management.action_qlk_project", raise_if_not_found=False),
            "tasks": self.env.ref("qlk_management.action_qlk_project_tasks", raise_if_not_found=False),
            "hours": self.env.ref("qlk_management.action_qlk_project_hours", raise_if_not_found=False),
        }
        action_payload = {key: {"id": action.id} for key, action in actions.items() if action}

        hr_payload = self._build_hr_dashboard_payload(user, employee_ids, allow_all)

        return {
            "user": {
                "name": user.name,
            },
            "is_manager": allow_all,
            "palette": {
                "primary": "#0F5CA8",
                "accent": "#22B6C8",
                "muted": "#0D3E7A",
                "success": "#27AE60",
            },
            "totals": {
                "total_projects": total_projects,
                "with_case": projects_with_case,
                "hours_total": round(hours_total, 2),
                "tasks_total": total_tasks,
                "department_counts": department_stats,
            },
            "projects": {
                "items": project_cards,
                "action": action_payload.get("projects"),
            },
            "tasks": {
                "total": total_tasks,
                "waiting": waiting_tasks,
                "approved": approved_tasks,
                "rejected": rejected_tasks,
                "hours": round(hours_total, 2),
                "action": action_payload.get("tasks"),
                "hours_action": action_payload.get("hours"),
            },
            "hr": hr_payload,
            "actions": action_payload,
        }
