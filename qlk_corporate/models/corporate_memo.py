# -*- coding: utf-8 -*-

from odoo import fields, models


class CorporateMemo(models.Model):
    _name = "qlk.corporate.memo"
    _description = "Corporate Memo"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Memo Title", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.corporate.case",
        string="Corporate Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Prepared By", tracking=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    body = fields.Html(string="Memo Content")
