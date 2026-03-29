# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    monthly_hours_target = fields.Float(string="Monthly Hours Target")
