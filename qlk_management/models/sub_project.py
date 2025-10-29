# -*- coding: utf-8 -*-
from odoo import models, fields, api

class subProject(models.Model):
    _name = "sub.project"

    name = fields.Char('Name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    partner_id = fields.Many2one('res.partner', string='Client')
    description = fields.Html('description')
    main_project_id = fields.Many2one(
            "main.project",
            string="Main Project",
            ondelete="cascade"
        )    
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments",
    )

    # task_ids = fields.One2many('task', 'sub_project_id', string='Tasks')
    # total_work_hours = fields.Float(string="Total Worked Hours", compute="")  

    
    # @api.depends('task_ids','task_ids.work_hours')
    # def _compute_task_ids_work_hours(self):
    #     for rec