# -*- coding: utf-8 -*-
from odoo import fields, models


class HREmployee(models.Model):
    _inherit = "hr.employee"

    lawyer_hour_cost = fields.Float(string="Lawyer Hour Cost")
