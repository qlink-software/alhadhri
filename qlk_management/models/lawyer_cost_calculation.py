# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LawyerCostCalculation(models.Model):
    _name = "lawyer.cost.calculation"
    _description = "Lawyer Cost Calculation"

    partner_id = fields.Many2one("res.partner", string="Lawyer", required=True, index=True)
    cost_per_hour_base = fields.Float(string="Base Cost Per Hour", required=True)
    profit_ratio = fields.Float(string="Profit Ratio", required=True, default=1.0)
    cost_per_hour = fields.Float(string="Cost Per Hour", compute="_compute_cost_per_hour", store=True)

    _sql_constraints = [
        ("lawyer_cost_partner_unique", "unique(partner_id)", "Each lawyer can only have one cost record.")
    ]

    @api.depends("cost_per_hour_base", "profit_ratio")
    def _compute_cost_per_hour(self):
        for record in self:
            record.cost_per_hour = (record.cost_per_hour_base or 0.0) * (record.profit_ratio or 0.0)
