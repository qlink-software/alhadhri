# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CostCalculation(models.Model):
    _name = "cost.calculation"
    _description = "Employee Cost Calculation"

    name = fields.Char(string="Description")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    mactech = fields.Float(string="Mactech")
    email_charge = fields.Float(string="Email Charge")
    office_rent = fields.Float(string="Office Rent")
    printer_rent = fields.Float(string="Printer Rent")
    telephone = fields.Float(string="Telephone")
    salary = fields.Float(string="Salary")
    total = fields.Float(string="Total", compute="_compute_total", store=True)
    cost_per_hour = fields.Float(string="Cost Per Hour", compute="_compute_cost_per_hour", store=True)

    @api.depends(
        "mactech",
        "email_charge",
        "office_rent",
        "printer_rent",
        "telephone",
        "salary",
    )
    def _compute_total(self):
        for record in self:
            record.total = sum(
                [
                    record.mactech or 0.0,
                    record.email_charge or 0.0,
                    record.office_rent or 0.0,
                    record.printer_rent or 0.0,
                    record.telephone or 0.0,
                    record.salary or 0.0,
                ]
            )

    @api.depends("total")
    def _compute_cost_per_hour(self):
        for record in self:
            record.cost_per_hour = (record.total or 0.0) / 180.0
