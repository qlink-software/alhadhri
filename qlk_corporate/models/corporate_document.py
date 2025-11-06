# -*- coding: utf-8 -*-

from odoo import fields, models


class CorporateDocument(models.Model):
    _name = "qlk.corporate.document"
    _description = "Corporate Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Document Name", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.corporate.case",
        string="Corporate Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    document_type = fields.Selection(
        selection=[
            ("incorporation", "Incorporation Document"),
            ("commercial_register", "Commercial Register"),
            ("bylaws", "Company Bylaws"),
            ("license", "License"),
            ("other", "Other"),
        ],
        string="Document Type",
        default="other",
        tracking=True,
    )
    issuing_authority = fields.Char(string="Issuing Authority")
    issue_date = fields.Date(string="Issue Date")
    attachment_id = fields.Many2one("ir.attachment", string="Attachment", required=True)
    notes = fields.Text(string="Notes")
