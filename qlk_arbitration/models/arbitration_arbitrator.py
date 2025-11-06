# -*- coding: utf-8 -*-

from odoo import fields, models


class ArbitrationArbitrator(models.Model):
    _name = "qlk.arbitration.arbitrator"
    _description = "Arbitrator Register"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, tracking=True)
    expertise = fields.Char(string="Expertise", tracking=True)
    organization = fields.Char(string="Organization", tracking=True)
    country_id = fields.Many2one("res.country", string="Country", tracking=True)
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    case_ids = fields.Many2many(
        "qlk.arbitration.case",
        string="Arbitration Cases",
        relation="qlk_arbitration_case_rel",
        column1="arbitrator_id",
        column2="case_id",
    )
