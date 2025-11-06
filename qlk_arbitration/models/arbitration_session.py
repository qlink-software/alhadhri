# -*- coding: utf-8 -*-

from odoo import fields, models


class ArbitrationSession(models.Model):
    _name = "qlk.arbitration.session"
    _description = "Arbitration Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Session Title", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.arbitration.case",
        string="Arbitration Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    session_date = fields.Datetime(string="Session Date", required=True, tracking=True)
    arbitrator_id = fields.Many2one("qlk.arbitration.arbitrator", string="Arbitrator", tracking=True)
    notes = fields.Text(string="Notes")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
