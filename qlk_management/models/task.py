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
    receive_date = fields.Datetime(string="Receive Date", tracking=True)
    delivery_date = fields.Datetime(string="Delivery Date", tracking=True)
    required_hours = fields.Float(
        string="Required Hours",
        required=True,
        tracking=True,
        digits="Product Unit of Measure",
    )
    priority = fields.Selection([
        ('high', 'High'),('medium', 'Medium'),('low', 'Low'),
    ], string='Priority', tracking=True)
    sub_project_id = fields.Many2one('sub.project', string='Sub Project')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments",)
    proposal_id = fields.Many2one('bd.proposal', string='Proposal')   
    # agreement_id = fields.Many2one('managment.agreement', string='Agreement')   
    crm_id = fields.Many2one('crm.lead', string='Crm')  
    partner_id = fields.Many2one('res.partner', string='Contact') 
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        index=True,
    )
    
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

    @api.constrains("required_hours")
    def _check_required_hours(self):
        for record in self:
            if record.required_hours <= 0:
                raise ValidationError("Required Hours must be strictly positive for '%s' task" % record.name)

    def _ensure_required_hours(self):
        missing = self.filtered(lambda record: record.required_hours <= 0)
        if missing:
            raise ValidationError("Required Hours must be strictly positive before saving or closing a task")

    @api.constrains("receive_date", "delivery_date")
    def _check_receive_delivery_dates(self):
        for record in self:
            if record.receive_date and record.delivery_date and record.delivery_date < record.receive_date:
                raise ValidationError("Delivery Date cannot be before Receive Date for '%s' task" % record.name)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_required_hours()
        records._send_assignment_email()
        return records

    def write(self, vals):
        old_users = {record.id: record.user_id for record in self}
        result = super().write(vals)
        self._ensure_required_hours()
        if "user_id" in vals:
            for record in self:
                if record.user_id and old_users.get(record.id) != record.user_id:
                    record._send_assignment_email()
        return result

    def _send_assignment_email(self):
        template = self.env.ref("qlk_management.mail_template_management_task_assignment", raise_if_not_found=False)
        if not template:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for record in self.filtered("user_id"):
            email_to = record.user_id.partner_id.email or record.user_id.email
            if not email_to:
                continue
            template.send_mail(record.id, force_send=False, email_values={"email_to": email_to})
            if activity_type:
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=record.user_id.id,
                    summary="New assigned task",
                    note="You have been assigned to task: %s" % record.display_name,
                )


    def confirm_acrion(self):
        for rec in self:
            rec.state = "confrim"

    def done_acrion(self):
        for rec in self:
            rec._ensure_required_hours()
            rec.state = "done"
    
    def reject_acrion(self):
        for rec in self:
            rec.state = "reject"

    def cancel_acrion(self):
        for rec in self:
            rec.state = "cancel"
