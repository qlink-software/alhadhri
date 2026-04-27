# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CorporateCaseProject(models.Model):
    _inherit = "qlk.corporate.case"

    engagement_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    agreement_hours = fields.Float(string="Agreement Hours", tracking=True)
    agreement_start_date = fields.Date(string="Agreement Start Date", tracking=True)
    agreement_end_date = fields.Date(string="Agreement End Date", tracking=True)
    actual_hours_total = fields.Float(string="Approved Hours", compute="_compute_project_hours", store=False)
    actual_hours_month = fields.Float(string="Approved Hours (Month)", compute="_compute_project_hours", store=False)
    over_hours = fields.Boolean(string="Over Agreement Hours", compute="_compute_project_hours", store=False)
    client_capacity = fields.Char(string="Client Capacity/Title")
    # client_document_ids = fields.One2many(
    #     related="client_id.client_document_ids",
    #     string="Client Documents",
    #     readonly=True,
    # )

    @api.depends("engagement_id", "agreement_hours")
    def _compute_project_hours(self):
        Task = self.env["qlk.task"]
        approved_states = {"approved"}
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for record in self:
            record.actual_hours_total = 0.0
            record.actual_hours_month = 0.0
            record.over_hours = False
            domain = []
            if not record.engagement_id:
                continue
            domain = [("engagement_id", "=", record.engagement_id.id)]
            domain.append(("approval_state", "in", list(approved_states)))
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
        if not self.engagement_id:
            return False
        domain = [("engagement_id", "=", self.engagement_id.id)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Hours"),
            "res_model": "qlk.task",
            "view_mode": "list,form",
            "domain": domain,
        }

    @api.onchange("engagement_id")
    def _onchange_engagement_id(self):
        for record in self:
            engagement = record.engagement_id
            if not engagement:
                continue
            if engagement.partner_id and not record.client_id:
                record.client_id = engagement.partner_id.id
            if engagement.lawyer_employee_id and not record.responsible_employee_id:
                record.responsible_employee_id = engagement.lawyer_employee_id.id

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("skip_engagement_service_validation"):
            for vals in vals_list:
                engagement = self.env["bd.engagement.letter"].browse(vals.get("engagement_id"))
                if engagement and engagement.service_type not in ("corporate", "mixed"):
                    raise UserError(_("This engagement letter does not allow corporate records."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("engagement_id") and not self.env.context.get("skip_engagement_service_validation"):
            engagement = self.env["bd.engagement.letter"].browse(vals["engagement_id"])
            if engagement and engagement.service_type not in ("corporate", "mixed"):
                raise UserError(_("This engagement letter does not allow corporate records."))
        return super().write(vals)
