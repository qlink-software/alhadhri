# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CostCalculation(models.Model):
    _name = "cost.calculation"

    name = fields.Char('Description')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    mactech = fields.Float('Mactech')
    email_charge = fields.Float('Email Charge')
    office_rent = fields.Float('Office Rent')
    printer_rent = fields.Float('Printer Rent')
    telephone = fields.Float('Telephone')
    salary = fields.Float('Salary')
    total = fields.Float('Total',compute='_compute_total', store=True)
    cost_per_hour = fields.Float('Cost Per Hour',compute='_compute_cost_per_hour')

    @api.depends('mactech', 'email_charge', 'office_rent', 'printer_rent', 'telephone', 'salary')
    def _compute_total(self):
        for rec in self:
            rec.total = sum([
                rec.mactech or 0.0,
                rec.email_charge or 0.0,
                rec.office_rent or 0.0,
                rec.printer_rent or 0.0,
                rec.telephone or 0.0,
                rec.salary or 0.0
            ])


    @api.depends('total')
    def _compute_cost_per_hour(self):
        for record in self:
            record.cost_per_hour = record.total / 180