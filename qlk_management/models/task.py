# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Tasks(models.Model):
    _name = "task"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char('Name')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('confrim', 'Confirm'),
        ('done', 'Done'),
        ('reject', 'Rejected'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft',)
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda res: res.env.user.id)
    description = fields.Html('description')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    priority = fields.Selection([
        ('high', 'High'),('medium', 'Medium'),('low', 'Low'),
    ], string='Priority', tracking=True)
    sub_project_id = fields.Many2one('sub.project', string='Sub Project')
    main_project_id = fields.Many2one('main.project', string='Main Project')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments",)
    proposal_id = fields.Many2one('sale.order', string='Proposal')   
    agreement_id = fields.Many2one('managment.agreement', string='Agreement')   
    crm_id = fields.Many2one('crm.lead', string='Crm')  
    partner_id = fields.Many2one('res.partner', string='Contact') 
    
    work_hours = fields.Float(string="Work Hours", help="Please Enter Your Hours ", required=True)  
    work_hours_display = fields.Char(
        string="Work Hours (HH:MM)", compute="_compute_work_hours_display"
    )

    @api.depends("work_hours")
    def _compute_work_hours_display(self):
        for rec in self:
            hours = int(rec.work_hours)
            minutes = int(round((rec.work_hours - hours) * 100))
            rec.work_hours_display = f"{hours:02d}:{minutes:02d}"


    # constraint for work_hours to check the mintes limit
    @api.constrains('work_hours')
    def _check_work_hours_limit(self):
        for res in self:
            if res.work_hours:
                hours = int(res.work_hours)
                minutes = int(round((res.work_hours - hours) * 100))
                if minutes >= 60:
                    raise ValidationError("Minutes cannot be 60 or more for ' %s 'task" %res.name)
                

    # constraint for work_hours to check the use enter his working hours
    @api.constrains('work_hours')
    def _check_work_login_work_hours(self):
        for record in self:
            if not record.work_hours:
                raise ValidationError("You Have to enter your Working Hours for' %s 'task" %record.name)


    def confirm_acrion(self):
        for rec in self:
            rec.state = "confrim"

    def done_acrion(self):
        for rec in self:
            rec.state = "done"
    
    def reject_acrion(self):
        for rec in self:
            rec.state = "reject"

    def cancel_acrion(self):
        for rec in self:
            rec.state = "cancel"