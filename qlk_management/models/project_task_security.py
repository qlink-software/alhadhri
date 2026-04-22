# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


class ProjectTask(models.Model):
    _inherit = "project.task"

    user_id = fields.Many2one(
        "res.users",
        string="Primary Assignee",
        compute="_compute_primary_user_id",
        inverse="_inverse_primary_user_id",
        store=True,
        index=True,
        help="Stored primary assignee used by strict lawyer record rules.",
    )

    @api.depends("user_ids")
    def _compute_primary_user_id(self):
        # Odoo 18 uses user_ids; this alias keeps security domains simple and indexed.
        for task in self:
            task.user_id = task.user_ids[:1] if task.user_ids else False

    def _inverse_primary_user_id(self):
        for task in self:
            task.user_ids = [Command.set([task.user_id.id])] if task.user_id else [Command.clear()]
