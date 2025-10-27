# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.osv.expression import OR


class QlkProjectDashboard(models.AbstractModel):
    _name = "qlk.project.dashboard"
    _description = "Project Dashboard Service"

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

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        lang = user.lang or "en_US"
        employee_ids = user.employee_ids.ids
        allow_all = user.has_group("qlk_law.group_qlk_law_manager") or user.has_group("base.group_system")

        project_model = self.env["qlk.project"]
        project_domain = self._project_domain(employee_ids, user, allow_all)
        projects = project_model.search(project_domain, order="write_date desc", limit=10)
        total_projects = project_model.search_count(project_domain)
        projects_with_case = project_model.search_count(OR([project_domain, [("case_id", "!=", False)]])) if project_domain else project_model.search_count([("case_id", "!=", False)])

        department_labels = {
            "pre_litigation": _("Pre-Litigation"),
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

        stage_stats = []
        stage_read = project_model.read_group(project_domain, ["stage_id"], ["stage_id"])
        for entry in stage_read:
            stage_ref = entry.get("stage_id")
            if not stage_ref:
                continue
            stage_stats.append(
                {
                    "id": stage_ref[0],
                    "name": stage_ref[1],
                    "count": entry.get("stage_id_count", 0),
                }
            )
        stage_stats.sort(key=lambda s: s["count"], reverse=True)

        project_ids = projects.ids if projects else []
        Task = self.env["qlk.task"]
        task_domain = [("project_id", "!=", False)]
        if not allow_all:
            if project_ids:
                task_domain.append(("project_id", "in", project_ids))
            else:
                task_domain.append(("assigned_user_id", "=", user.id))

        total_tasks = Task.search_count(task_domain)
        waiting_tasks = Task.search_count(task_domain + [("approval_state", "=", "waiting")])
        approved_tasks = Task.search_count(task_domain + [("approval_state", "=", "approved")])
        rejected_tasks = Task.search_count(task_domain + [("approval_state", "=", "rejected")])

        hours_total = 0.0
        hours_group = Task.read_group(task_domain + [("approval_state", "=", "approved")], ["hours_spent"], [])
        if hours_group:
            hours_total = hours_group[0].get("hours_spent", 0.0) or 0.0

        task_map = defaultdict(lambda: {"count": 0, "hours": 0.0})
        if project_ids:
            grouped = Task.read_group(task_domain, ["hours_spent", "project_id"], ["project_id"])
            for entry in grouped:
                project_ref = entry.get("project_id")
                if not project_ref:
                    continue
                project_id = project_ref[0]
                task_map[project_id]["count"] = entry.get("project_id_count", 0)
                task_map[project_id]["hours"] = entry.get("hours_spent", 0.0) or 0.0

        stage_model = self.env["qlk.project.stage"]
        stage_max_map = {}
        stage_max_read = stage_model.read_group([], ["sequence:max"], ["stage_type"])
        for entry in stage_max_read:
            stage_type = entry.get("stage_type")
            if stage_type:
                stage_max_map[stage_type] = entry.get("sequence_max", 0)

        project_cards = []
        for project in projects:
            max_sequence = stage_max_map.get(project.stage_type_code or project.department, project.stage_id.sequence or 1.0)
            progress = 0.0
            if max_sequence:
                progress = (project.stage_id.sequence or 0.0) / max_sequence
            project_cards.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "code": project.code or "",
                    "client": project.client_id.name if project.client_id else "",
                    "department": department_labels.get(project.department, project.department),
                    "stage": project.stage_id.name if project.stage_id else "",
                    "has_case": bool(project.case_id),
                    "tasks": task_map[project.id]["count"],
                    "hours": round(task_map[project.id]["hours"], 2),
                    "progress": round(progress, 2),
                    "url": {"res_model": "qlk.project", "res_id": project.id},
                }
            )

        actions = {
            "projects": self.env.ref("qlk_project_management.action_qlk_project", raise_if_not_found=False),
            "tasks": self.env.ref("qlk_project_management.action_qlk_project_tasks", raise_if_not_found=False),
            "hours": self.env.ref("qlk_project_management.action_qlk_project_hours", raise_if_not_found=False),
            "stages": self.env.ref("qlk_project_management.action_qlk_project_stage", raise_if_not_found=False),
        }
        action_payload = {key: {"id": action.id} for key, action in actions.items() if action}

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
            "stages": stage_stats,
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
            "actions": {
                **action_payload,
            },
        }

