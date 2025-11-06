# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProposalPricingTable(models.Model):
    _name = "qlk.pricing.table"
    _description = "Proposal Pricing Table"
    _order = "company_id, name"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    avg_case_cost = fields.Monetary(string="Average Case Cost", required=True, currency_field="currency_id")
    description = fields.Text(string="Notes")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_company_unique", "unique(name, company_id)", "Each company must have unique pricing table names."),
    ]

    @api.constrains("avg_case_cost")
    def _check_avg_case_cost(self):
        for record in self:
            if record.avg_case_cost < 0.0:
                raise ValidationError(_("The average case cost must be positive."))
