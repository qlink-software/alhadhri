# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    engagement_client_code = fields.Char(
        string="Engagement Client Code",
        copy=False,
    )

    _sql_constraints = [
        (
            "engagement_client_code_unique",
            "unique(engagement_client_code)",
            "The engagement client code must be unique.",
        ),
    ]
