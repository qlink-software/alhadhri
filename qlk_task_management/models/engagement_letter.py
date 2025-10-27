# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class EngagementLetter(models.Model):
    _inherit = "qlk.engagement.letter"

    task_ids = fields.One2many(
        "qlk.task",
        "engagement_id",
        string="Corporate Tasks",
    )
    task_hours_total = fields.Float(
        string="Approved Task Hours",
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
        engagements = self.filtered(lambda record: record.id)
        if not engagements:
            for record in self:
                record.task_hours_total = 0.0
                record.task_waiting_count = 0
            return

        engagement_ids = engagements.ids
        base_domain = [
            ("engagement_id", "in", engagement_ids),
            ("department", "=", "corporate"),
        ]

        approved_groups = Task.read_group(
            base_domain + [("approval_state", "=", "approved")],
            ["hours_spent", "engagement_id"],
            ["engagement_id"],
        )
        approved_map = {engagement_id: 0.0 for engagement_id in engagement_ids}
        for entry in approved_groups:
            engagement_ref = entry.get("engagement_id")
            if engagement_ref:
                approved_map[engagement_ref[0]] = entry.get("hours_spent", 0.0)

        waiting_groups = Task.read_group(
            base_domain + [("approval_state", "=", "waiting")],
            ["engagement_id"],
            ["engagement_id"],
        )
        waiting_map = {engagement_id: 0 for engagement_id in engagement_ids}
        for entry in waiting_groups:
            engagement_ref = entry.get("engagement_id")
            if engagement_ref:
                waiting_map[engagement_ref[0]] = entry.get("engagement_id_count", 0)

        for record in self:
            if not record.id:
                record.task_hours_total = 0.0
                record.task_waiting_count = 0
                continue
            record.task_hours_total = approved_map.get(record.id, 0.0)
            record.task_waiting_count = waiting_map.get(record.id, 0)

    def action_open_corporate_tasks(self):
        self.ensure_one()
        action = self.env.ref("qlk_task_management.action_qlk_task_corporate").read()[0]
        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        action["context"] = {
            **context,
            "default_department": "corporate",
            "default_engagement_id": self.id,
            "search_default_group_month": 1,
        }
        action["domain"] = [("department", "=", "corporate"), ("engagement_id", "=", self.id)]
        return action
