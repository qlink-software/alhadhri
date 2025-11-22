# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class CostCalculation(models.Model):
    _name = "cost.calculation"
    _description = "Lawyer Cost Calculation"

    name = fields.Char(string="Reference", required=True, default=lambda self: _("New"))
    employee_id = fields.Many2one("hr.employee", string="Lawyer", required=True)
    lawyer_hour_cost = fields.Float(
        string="Lawyer Hour Cost", related="employee_id.lawyer_hour_cost", store=True, readonly=False
    )
    mactech = fields.Float(string="Mactech")
    email_charge = fields.Float(string="Email Charge")
    office_rent = fields.Float(string="Office Rent")
    printer_rent = fields.Float(string="Printer Rent")
    telephone = fields.Float(string="Telephone")
    salary = fields.Float(string="Salary")
    total = fields.Float(string="Total", compute="_compute_totals", store=True)
    cost_per_hour = fields.Float(string="Cost Per Hour", compute="_compute_totals", store=True)

    _sql_constraints = [
        ("cost_calculation_employee_unique", "unique(employee_id)", "Each lawyer can only have one cost record.")
    ]

    @api.onchange("employee_id")
    def _onchange_employee(self):
        for record in self:
            if record.employee_id and record.name in (False, _("New")):
                record.name = f"{record.employee_id.name} Cost"

    @api.depends("mactech", "email_charge", "office_rent", "printer_rent", "telephone", "salary", "lawyer_hour_cost")
    def _compute_totals(self):
        for record in self:
            overhead = sum(
                [
                    record.mactech,
                    record.email_charge,
                    record.office_rent,
                    record.printer_rent,
                    record.telephone,
                    record.salary,
                ]
            )
            record.total = overhead + (record.lawyer_hour_cost or 0.0)
            record.cost_per_hour = record.total / 180.0 if record.total else 0.0
