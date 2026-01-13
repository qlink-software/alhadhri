# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ArbitrationCaseProject(models.Model):
    _inherit = "qlk.arbitration.case"

    project_id = fields.Many2one(
        "qlk.project",
        string="Linked Project",
        domain="[('department', '=', 'arbitration')]",
        tracking=True,
    )
    agreement_hours = fields.Float(string="Agreement Hours", tracking=True)
    agreement_start_date = fields.Date(string="Agreement Start Date", tracking=True)
    agreement_end_date = fields.Date(string="Agreement End Date", tracking=True)
    actual_hours_total = fields.Float(string="Approved Hours", compute="_compute_project_hours", store=False)
    actual_hours_month = fields.Float(string="Approved Hours (Month)", compute="_compute_project_hours", store=False)
    over_hours = fields.Boolean(string="Over Agreement Hours", compute="_compute_project_hours", store=False)
    client_capacity = fields.Char(string="Client Capacity/Title")
    client_document_ids = fields.One2many(
        related="claimant_id.client_document_ids",
        string="Client Documents",
    )

    @api.depends("project_id", "agreement_hours")
    def _compute_project_hours(self):
        Task = self.env["qlk.task"]
        approved_states = {"approved"}
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
    
        for record in self:
            record.actual_hours_total = 0.0
            record.actual_hours_month = 0.0
            record.over_hours = False
            if not record.project_id:
                continue
            domain = [
                ("project_id", "=", record.project_id.id),
                ("approval_state", "in", list(approved_states)),
            ]
            tasks = Task.search(domain)
            total = sum(tasks.mapped("hours_spent"))
            month_hours = sum(
                task.hours_spent
                for task in tasks
                if task.date_start and task.date_start >= month_start
            )
            record.actual_hours_total = total
            record.actual_hours_month = month_hours
            if record.agreement_hours:
                record.over_hours = total > record.agreement_hours

    def action_open_project_hours(self):
        self.ensure_one()
        if not self.project_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Project Tasks"),
            "res_model": "qlk.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.project_id.id)],
        }
