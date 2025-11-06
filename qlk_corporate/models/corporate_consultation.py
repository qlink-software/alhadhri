# -*- coding: utf-8 -*-

from odoo import fields, models


class CorporateConsultation(models.Model):
    _name = "qlk.corporate.consultation"
    _description = "Corporate Consultation"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Subject", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.corporate.case",
        string="Corporate Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    consultation_date = fields.Date(string="Consultation Date", default=fields.Date.context_today, tracking=True)
    fee_amount = fields.Float(string="Fee Amount")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    notes = fields.Text(string="Notes")
