# -*- coding: utf-8 -*-

from odoo import fields, models


class ArbitrationAward(models.Model):
    _name = "qlk.arbitration.award"
    _description = "Arbitration Award"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Award Title", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.arbitration.case",
        string="Arbitration Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    decision_date = fields.Date(string="Decision Date", default=fields.Date.context_today, tracking=True)
    enforcement_body = fields.Char(string="Enforcement Body")
    attachment_id = fields.Many2one("ir.attachment", string="Award Document")
    notes = fields.Text(string="Notes")
