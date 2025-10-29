# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MainProject(models.Model):
    _name = "main.project"

    name = fields.Char('Name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    partner_id = fields.Many2one('res.partner', string='Client')
    description = fields.Html('description')
    sub_project_ids = fields.One2many(
        "sub.project",
        "main_project_id",
        string="Sub Projects"
    )

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments",
    )
    
    # def _compute_project_code(self):
    #     for rec in self:
    #         if rec['type_project'] == 'corporate':
    #             rec.name = "C" + rec.client_code
    #         elif rec['type_project'] == 'litigation':
    #             rec.name = "L" + rec.client_code
    #         else:
    #             rec.name = "CL" + rec.client_code
    #     return rec