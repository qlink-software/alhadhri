# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    cost_calculation_id = fields.Many2one("cost.calculation", string="Cost Calculation")
    lawyer_id = fields.Many2one("hr.employee", string="Lawyer")
    lawyer_hour_cost = fields.Float(string="Lawyer Hour Cost", compute="_compute_lawyer_costs", store=True)
    lawyer_hours = fields.Float(string="Lawyer Hours")
    lawyer_total_cost = fields.Float(string="Lawyer Total Cost", compute="_compute_totals", store=True)
    additional_project_cost = fields.Float(string="Additional Project Cost")
    total_cost_all = fields.Float(string="Total Cost", compute="_compute_totals", store=True)

    @api.depends("lawyer_id")
    def _compute_lawyer_costs(self):
        for project in self:
            project.lawyer_hour_cost = project.lawyer_id.lawyer_hour_cost or 0.0

    @api.depends("lawyer_hour_cost", "lawyer_hours", "additional_project_cost")
    def _compute_totals(self):
        for project in self:
            total = (project.lawyer_hour_cost or 0.0) * (project.lawyer_hours or 0.0)
            project.lawyer_total_cost = total
            project.total_cost_all = total + (project.additional_project_cost or 0.0)
