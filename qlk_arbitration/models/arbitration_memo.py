# -*- coding: utf-8 -*-

from odoo import fields, models


class ArbitrationMemo(models.Model):
    _name = "qlk.arbitration.memo"
    _description = "Arbitration Memo"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Memo Title", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.arbitration.case",
        string="Arbitration Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    memo_type = fields.Selection(
        selection=[
            ("claim", "Statement of Claim"),
            ("defense", "Statement of Defense"),
            ("rejoinder", "Rejoinder"),
            ("other", "Other"),
        ],
        string="Memo Type",
        default="other",
        tracking=True,
    )
    submission_date = fields.Date(string="Submission Date", default=fields.Date.context_today, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Prepared By", tracking=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    body = fields.Html(string="Memo Content")
