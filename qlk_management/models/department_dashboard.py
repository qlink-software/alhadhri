# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.osv.expression import AND, OR
from odoo.tools.misc import format_date


class QlkDepartmentDashboard(models.AbstractModel):
    _name = "qlk.department.dashboard"
    _description = "Personal Corporate and Arbitration Dashboard Service"

    _CONFIG = {
        "corporate": {
            "groups": (
                "qlk_corporate.group_corporate_user",
                "qlk_corporate.group_corporate_manager",
            ),
            "title": "Corporate Dashboard",
            "subtitle": "Your corporate projects, matters, contracts and tasks in one workspace.",
            "matter_model": "qlk.corporate.case",
            "matter_action": "qlk_corporate.action_corporate_case",
            "matter_label": "Corporate Matters",
            "matter_icon": "fa-building-o",
            "open_states": ("draft", "in_progress", "waiting"),
        },
        "arbitration": {
            "groups": (
                "qlk_arbitration.group_arbitration_user",
                "qlk_arbitration.group_arbitration_manager",
            ),
            "title": "Arbitration Dashboard",
            "subtitle": "Your arbitration projects, cases, sessions and tasks in one workspace.",
            "matter_model": "qlk.arbitration.case",
            "matter_action": "qlk_arbitration.action_arbitration_case",
            "matter_label": "Arbitration Cases",
            "matter_icon": "fa-gavel",
            "open_states": ("draft", "in_progress", "waiting_award"),
        },
    }

    @api.model
    def _action(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return {"id": action.id} if action else False

    @api.model
    def _personal_domain(self, model_name):
        """Return direct assignments only; managers also land on their own workspace."""
        if model_name not in self.env:
            return [("id", "=", 0)]
        model = self.env[model_name]
        employees = self.env.user.employee_ids
        if not employees:
            employees = self.env["hr.employee"].sudo().with_context(active_test=False).search(
                [("user_id", "=", self.env.user.id)]
            )
        employee_ids = employees.ids
        if not employee_ids:
            return [("id", "=", 0)]
        scopes = []
        # التعيين الشخصي في الداشبورد يعتمد على سجل الموظف، لا على res.users.
        for field_name in (
            "lawyer_id",
            "lawyer_employee_id",
            "responsible_employee_id",
            "employee_id",
        ):
            field = model._fields.get(field_name)
            if field and field.comodel_name == "hr.employee":
                scopes.append([(field_name, "in", employee_ids)])
        if "employee_ids" in model._fields:
            scopes.append([("employee_ids", "in", employee_ids)])
        if not scopes:
            return [("id", "=", 0)]
        return OR(scopes)

    @api.model
    def _project_domain(self, department):
        service_domain = [
            "|",
            ("service_category", "=", department),
            ("service_type", "=", department),
        ]
        return AND([service_domain, self._personal_domain("qlk.project")])

    @api.model
    def _matter_domain(self, department):
        model_name = self._CONFIG[department]["matter_model"]
        return self._personal_domain(model_name)

    @api.model
    def _task_domain(self, department):
        return AND(
            [
                [("department", "=", department)],
                self._personal_domain("qlk.task"),
            ]
        )

    @api.model
    def _related_domain(self, relation_field, personal_domain):
        related = []
        for token in personal_domain:
            if isinstance(token, (list, tuple)) and len(token) == 3:
                related.append((f"{relation_field}.{token[0]}", token[1], token[2]))
            else:
                related.append(token)
        return related

    @api.model
    def _selection_label(self, record, field_name):
        field = record._fields.get(field_name)
        value = record[field_name] if field_name in record._fields else False
        if not field or not field.selection:
            return value or ""
        selection = field.selection
        if callable(selection):
            selection = field._description_selection(self.env)
        return dict(selection or []).get(value, value or "")

    @api.model
    def _format_date(self, value):
        if not value:
            return ""
        date_value = fields.Datetime.to_datetime(value).date()
        return format_date(self.env, date_value)

    @api.model
    def _count_card(self, key, label, model_name, domain, action, icon, tone="primary"):
        model = self.env[model_name] if model_name in self.env else None
        return {
            "key": key,
            "label": label,
            "count": model.search_count(domain) if model is not None else 0,
            "domain": domain,
            "action": self._action(action),
            "icon": icon,
            "tone": tone,
        }

    @api.model
    def _worked_hours(self, task_domain):
        if "qlk.task" not in self.env:
            return 0.0
        task_model = self.env["qlk.task"]
        domain = AND([task_domain, [("approval_state", "=", "approved")]])
        grouped = task_model.read_group(domain, ["hours_spent:sum"], [])
        return round((grouped and grouped[0].get("hours_spent") or 0.0), 2)

    @api.model
    def _projects(self, domain):
        projects = self.env["qlk.project"].search(domain, order="create_date desc, id desc", limit=6)
        return [
            {
                "id": project.id,
                "name": project.name or project.service_code or _("Project"),
                "code": project.service_code or "",
                "client": project.client_id.display_name or "",
                "state": self._selection_label(project, "state"),
                "state_value": project.state or "draft",
                "planned_hours": round(project.planned_hours or 0.0, 2),
                "consumed_hours": round(project.consumed_hours or 0.0, 2),
                "remaining_hours": round(project.remaining_hours or 0.0, 2),
                "usage_percent": min(max(round(project.hours_usage_percent or 0.0, 1), 0), 100),
                "hours_state": project.hours_state or "normal",
                "url": {"res_model": "qlk.project", "res_id": project.id},
            }
            for project in projects
        ]

    @api.model
    def _matters(self, department, domain):
        model_name = self._CONFIG[department]["matter_model"]
        records = self.env[model_name].search(domain, order="create_date desc, id desc", limit=6)
        result = []
        for record in records:
            if department == "corporate":
                reference = record.client_id.display_name or ""
                meta = self._selection_label(record, "service_type")
            else:
                reference = record.case_number or ""
                meta = record.arbitration_center or ""
            result.append(
                {
                    "id": record.id,
                    "name": record.display_name,
                    "reference": reference,
                    "meta": meta,
                    "state": self._selection_label(record, "state"),
                    "state_value": record.state or "draft",
                    "url": {"res_model": model_name, "res_id": record.id},
                }
            )
        return result

    @api.model
    def _tasks(self, domain):
        tasks = self.env["qlk.task"].search(domain, order="delivery_date asc, date_start desc, id desc", limit=6)
        return [
            {
                "id": task.id,
                "name": task.display_name,
                "priority": self._selection_label(task, "priority"),
                "priority_value": task.priority or "medium",
                "state": self._selection_label(task, "completion_state"),
                "date": self._format_date(task.delivery_date or task.date_finished or task.date_start),
                "hours": round(task.hours_spent or 0.0, 2),
                "url": {"res_model": "qlk.task", "res_id": task.id},
            }
            for task in tasks
        ]

    @api.model
    def _schedule(self, department, matter_domain):
        if department == "arbitration":
            model_name = "qlk.arbitration.session"
            date_field = "session_date"
            domain = AND(
                [
                    self._related_domain("case_id", matter_domain),
                    [(date_field, ">=", fields.Datetime.now())],
                ]
            )
            action = "qlk_arbitration.action_arbitration_session"
        else:
            model_name = "qlk.corporate.contract"
            date_field = "end_date"
            domain = AND(
                [
                    self._related_domain("case_id", matter_domain),
                    [(date_field, ">=", fields.Date.context_today(self))],
                ]
            )
            action = "qlk_corporate.action_corporate_contract"
        records = self.env[model_name].search(domain, order=f"{date_field} asc, id desc", limit=6)
        return {
            "action": self._action(action),
            "domain": domain,
            "items": [
                {
                    "id": record.id,
                    "name": record.display_name,
                    "matter": record.case_id.display_name or "",
                    "date": self._format_date(record[date_field]),
                    "url": {"res_model": model_name, "res_id": record.id},
                }
                for record in records
            ],
        }

    @api.model
    def _state_summary(self, domain):
        model = self.env["qlk.project"]
        labels = dict(model._fields["state"].selection)
        groups = model.read_group(domain, ["state"], ["state"], lazy=False)
        return [
            {
                "key": item.get("state") or "unassigned",
                "label": labels.get(item.get("state"), _("Unassigned")),
                "count": item.get("__count", 0),
                "domain": AND([domain, [("state", "=", item.get("state"))]]),
            }
            for item in groups
            if item.get("state")
        ]

    @api.model
    def get_dashboard_data(self, department):
        config = self._CONFIG.get(department)
        if not config or not any(self.env.user.has_group(group) for group in config["groups"]):
            return {
                "access_denied": True,
                "cards": [],
                "projects": [],
                "matters": [],
                "tasks": [],
                "labels": {"access_denied": _("Access denied")},
            }

        user = self.env.user
        project_domain = self._project_domain(department)
        matter_domain = self._matter_domain(department)
        task_domain = self._task_domain(department)
        open_domain = AND([matter_domain, [("state", "in", list(config["open_states"]))]])

        cards = [
            self._count_card(
                "projects", _("My Projects"), "qlk.project", project_domain,
                "qlk_management.action_qlk_project", "fa-briefcase", "primary",
            ),
            self._count_card(
                "matters", _(config["matter_label"]), config["matter_model"], matter_domain,
                config["matter_action"], config["matter_icon"], "accent",
            ),
            self._count_card(
                "open", _("Open Matters"), config["matter_model"], open_domain,
                config["matter_action"], "fa-folder-open", "warning",
            ),
            self._count_card(
                "tasks", _("My Tasks"), "qlk.task", task_domain,
                "qlk_task_management.action_qlk_task_all", "fa-check-square-o", "success",
            ),
        ]

        if department == "corporate":
            contract_domain = self._related_domain("case_id", matter_domain)
            cards.append(
                self._count_card(
                    "contracts", _("Contracts"), "qlk.corporate.contract", contract_domain,
                    "qlk_corporate.action_corporate_contract", "fa-file-text-o", "muted",
                )
            )
        else:
            session_domain = self._related_domain("case_id", matter_domain)
            cards.append(
                self._count_card(
                    "sessions", _("Sessions"), "qlk.arbitration.session", session_domain,
                    "qlk_arbitration.action_arbitration_session", "fa-calendar", "muted",
                )
            )

        return {
            "access_denied": False,
            "department": department,
            "title": _(config["title"]),
            "subtitle": _(config["subtitle"]),
            "user": {
                "name": user.name,
                "company": user.company_id.display_name,
            },
            "palette": {
                "primary": "#0F5CA8" if department == "corporate" else "#5B3A8E",
                "accent": "#22B6C8" if department == "corporate" else "#C5963D",
                "muted": "#0D3E7A" if department == "corporate" else "#342052",
                "success": "#27AE60",
            },
            "cards": cards,
            "worked_hours": self._worked_hours(task_domain),
            "project_count": self.env["qlk.project"].search_count(project_domain),
            "projects": self._projects(project_domain),
            "projects_action": self._action("qlk_management.action_qlk_project"),
            "projects_domain": project_domain,
            "project_states": self._state_summary(project_domain),
            "matters": self._matters(department, matter_domain),
            "matters_action": self._action(config["matter_action"]),
            "matters_domain": matter_domain,
            "tasks": self._tasks(task_domain),
            "tasks_action": self._action("qlk_task_management.action_qlk_task_all"),
            "tasks_domain": task_domain,
            "schedule": self._schedule(department, matter_domain),
            "labels": {
                "loading": _("Loading your workspace…"),
                "access_denied": _("Access denied"),
                "personal_workspace": _("Personal workspace"),
                "approved_hours": _("Approved hours"),
                "hour_short": _("h"),
                "overview": _("Workspace overview"),
                "overview_hint": _("Live figures restricted to your assignments"),
                "projects": _("My Projects"),
                "projects_hint": _("Only projects assigned to you in this department"),
                "matters": _(config["matter_label"]),
                "matters_hint": _("Your latest assigned matters"),
                "tasks": _("My Tasks"),
                "tasks_hint": _("Your department task queue"),
                "schedule": _("Upcoming Sessions") if department == "arbitration" else _("Contract Deadlines"),
                "schedule_hint": _("Your nearest scheduled dates"),
                "view_all": _("View all"),
                "no_projects": _("No projects assigned to you in this department."),
                "no_matters": _("No matters assigned to you."),
                "no_tasks": _("No tasks assigned to you."),
                "no_schedule": _("No upcoming dates."),
                "planned": _("Planned"),
                "consumed": _("Consumed"),
                "remaining": _("Remaining"),
                "hours": _("hours"),
            },
        }
