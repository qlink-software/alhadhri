# -*- coding: utf-8 -*-
from odoo import fields, models


class EngagementClientDetail(models.Model):
    _name = "qlk.engagement.client.detail"
    _description = "Engagement Client Detail"
    _order = "sequence, id"

    engagement_id = fields.Many2one(
        "qlk.engagement.letter",
        string="Engagement Letter",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Contact Name", required=True)
    role = fields.Char(string="Role / Title")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    identification = fields.Char(string="Identification Number")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)
