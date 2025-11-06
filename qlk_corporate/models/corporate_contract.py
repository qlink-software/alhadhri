# -*- coding: utf-8 -*-

from odoo import fields, models


class CorporateContract(models.Model):
    _name = "qlk.corporate.contract"
    _description = "Corporate Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Contract Title", required=True, tracking=True)
    case_id = fields.Many2one(
        "qlk.corporate.case",
        string="Corporate Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    contract_type = fields.Selection(
        selection=[
            ("nda", "Non-Disclosure Agreement"),
            ("services", "Services Agreement"),
            ("supply", "Supply Agreement"),
            ("franchise", "Franchise Agreement"),
            ("other", "Other"),
        ],
        string="Contract Type",
        default="other",
        tracking=True,
    )
    counterparty_id = fields.Many2one("res.partner", string="Counterparty", tracking=True)
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    auto_renew = fields.Boolean(string="Auto Renewal", tracking=True)
    contract_value = fields.Float(string="Contract Value")
    attachment_id = fields.Many2one("ir.attachment", string="Primary Document")
    description = fields.Html(string="Notes")
