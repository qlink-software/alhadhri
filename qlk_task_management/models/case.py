# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class Case(models.Model):
    _inherit = "qlk.case"

    task_ids = fields.One2many(
        "qlk.task",
        "case_id",
        string="Litigation Tasks",
    )
    task_hours_total = fields.Float(
        string="Approved Task Hours",
        compute="_compute_task_metrics",
        readonly=True,
    )
    task_hours_pre = fields.Float(
        string="Pre-Litigation Hours",
        compute="_compute_task_metrics",
        readonly=True,
    )
    task_hours_post = fields.Float(
        string="Post-Litigation Hours",
        compute="_compute_task_metrics",
        readonly=True,
    )
    task_waiting_count = fields.Integer(
        string="Tasks Awaiting Approval",
        compute="_compute_task_metrics",
        readonly=True,
    )

    def _compute_task_metrics(self):
        Task = self.env["qlk.task"]
        cases = self.filtered(lambda record: record.id)
        if not cases:
            for record in self:
                record.task_hours_total = 0.0
                record.task_hours_pre = 0.0
                record.task_hours_post = 0.0
                record.task_waiting_count = 0
            return

        case_ids = cases.ids
        base_domain = [
            ("case_id", "in", case_ids),
            ("department", "=", "litigation"),
        ]

        approved_groups = Task.read_group(
            base_domain + [("approval_state", "=", "approved")],
            ["hours_spent", "case_id", "litigation_phase"],
            ["case_id", "litigation_phase"],
        )
        total_map = {case_id: 0.0 for case_id in case_ids}
        pre_map = {case_id: 0.0 for case_id in case_ids}
        post_map = {case_id: 0.0 for case_id in case_ids}

        for entry in approved_groups:
            case_ref = entry.get("case_id")
            phase = entry.get("litigation_phase")
            hours_value = entry.get("hours_spent", 0.0)
            if not case_ref:
                continue
            case_id = case_ref[0]
            total_map[case_id] = total_map.get(case_id, 0.0) + hours_value
            if phase == "pre":
                pre_map[case_id] = pre_map.get(case_id, 0.0) + hours_value
            elif phase == "post":
                post_map[case_id] = post_map.get(case_id, 0.0) + hours_value

        waiting_groups = Task.read_group(
            base_domain + [("approval_state", "=", "waiting")],
            ["case_id"],
            ["case_id"],
        )
        waiting_map = {case_id: 0 for case_id in case_ids}
        for entry in waiting_groups:
            case_ref = entry.get("case_id")
            if case_ref:
                waiting_map[case_ref[0]] = entry.get("case_id_count", 0)

        for record in self:
            if not record.id:
                record.task_hours_total = 0.0
                record.task_hours_pre = 0.0
                record.task_hours_post = 0.0
                record.task_waiting_count = 0
                continue
            record.task_hours_total = total_map.get(record.id, 0.0)
            record.task_hours_pre = pre_map.get(record.id, 0.0)
            record.task_hours_post = post_map.get(record.id, 0.0)
            record.task_waiting_count = waiting_map.get(record.id, 0)

    def action_open_litigation_tasks(self):
        self.ensure_one()
        action = self.env.ref("qlk_task_management.action_qlk_task_litigation").read()[0]
        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        action["context"] = {
            **context,
            "default_department": "litigation",
            "default_case_id": self.id,
            "default_litigation_phase": self._guess_default_phase(),
            "search_default_group_month": 1,
        }
        action["domain"] = [("department", "=", "litigation"), ("case_id", "=", self.id)]
        return action

    def _guess_default_phase(self):
        self.ensure_one()
        # Simple helper to default the litigation phase when logging a task from the case.
        # Falls back to pre-litigation when the phase cannot be determined.
        phase_field = False
        for candidate in ("litigation_stage", "stage"):
            if candidate in self._fields:
                phase_field = candidate
                break
        if phase_field:
            value = getattr(self, phase_field)
            if hasattr(value, "technical_name"):
                technical = value.technical_name
                if technical in ("pre", "post"):
                    return technical
            if isinstance(value, str) and value in ("pre", "post"):
                return value
        return "pre"

    def action_send_case_sms(self):
        self.ensure_one()
        # Delegate to upstream implementation when present; otherwise return gracefully.
        parent_method = getattr(super(), "action_send_case_sms", None)
        if callable(parent_method):
            return parent_method()
        return False
