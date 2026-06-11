# -*- coding: utf-8 -*-
from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError


class Tasks(models.Model):
    _name = "task"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char('Name')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('confrim', 'In Progress'),
        ('done', 'Completed'),
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
    completed_by = fields.Many2one("res.users", string="Completed By", readonly=True, tracking=True)
    completed_date = fields.Datetime(string="Completed On", readonly=True, tracking=True)
    completion_reviewed_by = fields.Many2one(
        "res.users", string="Completion Reviewed By", readonly=True, tracking=True
    )
    completion_reviewed_date = fields.Datetime(
        string="Completion Reviewed On", readonly=True, tracking=True
    )
    can_mark_completed = fields.Boolean(compute="_compute_workflow_buttons")
    can_review_completion = fields.Boolean(compute="_compute_workflow_buttons")

    def _compute_workflow_buttons(self):
        current_user = self.env.user
        is_manager = current_user.has_group("qlk_task_management.group_task_manager")
        for task in self:
            task.can_mark_completed = task.state == "confrim" and task.user_id == current_user
            task.can_review_completion = (
                task.state == "done"
                and not task.completion_reviewed_by
                and (task.create_uid == current_user or is_manager)
            )

    @api.depends("work_hours")
    def _compute_work_hours_display(self):
        for rec in self:
            total_seconds = int(round((rec.work_hours or 0.0) * 3600))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            rec.work_hours_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"


    # constraint for work_hours to check the mintes limit
    @api.constrains('work_hours')
    def _check_work_hours_limit(self):
        for res in self:
            if res.work_hours:
                total_seconds = int(round((res.work_hours or 0.0) * 3600))
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                if minutes >= 60 or seconds >= 60:
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

    def _sync_hour_vals(self, vals):
        needs_required_hours = not self or any(record.required_hours <= 0 for record in self)
        needs_work_hours = not self or any(record.work_hours <= 0 for record in self)
        if vals.get("work_hours") and not vals.get("required_hours") and needs_required_hours:
            vals["required_hours"] = vals["work_hours"]
        if vals.get("required_hours") and not vals.get("work_hours") and needs_work_hours:
            vals["work_hours"] = vals["required_hours"]
        return vals

    @api.constrains("receive_date", "delivery_date")
    def _check_receive_delivery_dates(self):
        for record in self:
            if record.receive_date and record.delivery_date and record.delivery_date < record.receive_date:
                raise ValidationError("Delivery Date cannot be before Receive Date for '%s' task" % record.name)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sync_hour_vals(dict(vals)) for vals in vals_list]
        records = super().create(vals_list)
        records._ensure_required_hours()
        records._send_assignment_email()
        return records

    def write(self, vals):
        old_users = {record.id: record.user_id for record in self}
        old_states = {record.id: record.state for record in self}
        vals = self._sync_hour_vals(dict(vals))
        result = super().write(vals)
        self._ensure_required_hours()
        if "user_id" in vals:
            for record in self:
                if record.user_id and old_users.get(record.id) != record.user_id:
                    record._send_assignment_email()
        if vals.get("state") == "done":
            for record in self:
                if old_states.get(record.id) != "done":
                    if not record.completed_by:
                        record.completed_by = self.env.user
                    if not record.completed_date:
                        record.completed_date = fields.Datetime.now()
                    record._send_completion_notification()
        return result

    def _record_url(self):
        self.ensure_one()
        return "%s/web#id=%s&model=%s&view_type=form" % (
            self.get_base_url(),
            self.id,
            self._name,
        )

    def _send_assignment_email(self):
        template = self.env.ref("qlk_management.mail_template_management_task_assignment", raise_if_not_found=False)
        if not template:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for record in self.filtered("user_id"):
            email_to = record.user_id.partner_id.email or record.user_id.email
            partner = record.user_id.partner_id
            if partner:
                record.message_subscribe(partner_ids=[partner.id])
                record.message_post(
                    body=_(
                        "You have been assigned a new internal task/request.<br/>"
                        "<b>Task:</b> %(name)s<br/>"
                        "<b>Priority:</b> %(priority)s<br/>"
                        "<b>Deadline:</b> %(deadline)s<br/>"
                        "<b>Created By:</b> %(creator)s<br/>"
                        "<a href='%(url)s'>Open Task</a>"
                    ) % {
                        "name": record.display_name,
                        "priority": dict(record._fields["priority"].selection).get(record.priority, record.priority or "-"),
                        "deadline": record.delivery_date or record.end_date or "-",
                        "creator": record.create_uid.name,
                        "url": record._record_url(),
                    },
                    partner_ids=[partner.id],
                )
            if email_to:
                template.send_mail(record.id, force_send=False, email_values={"email_to": email_to})
            if activity_type:
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=record.user_id.id,
                    summary="New assigned task",
                    note="You have been assigned to task: %s" % record.display_name,
                )

    def _send_completion_notification(self):
        template = self.env.ref("qlk_management.mail_template_management_task_completion", raise_if_not_found=False)
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for record in self:
            creator = record.create_uid
            partner = creator.partner_id
            if partner:
                record.message_subscribe(partner_ids=[partner.id])
                record.message_post(
                    body=_("Task has been completed by %s.") % (record.completed_by.name or self.env.user.name),
                    partner_ids=[partner.id],
                )
            email_to = creator.partner_id.email or creator.email
            if template and email_to:
                template.send_mail(record.id, force_send=False, email_values={"email_to": email_to})
            if activity_type:
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=creator.id,
                    summary=_("Task completed"),
                    note=_("Task has been completed: %s") % record.display_name,
                )

    def confirm_acrion(self):
        for rec in self:
            rec.state = "confrim"

    def done_acrion(self):
        current_user = self.env.user
        for rec in self:
            rec._ensure_required_hours()
            if rec.user_id != current_user:
                raise UserError(_("Only the assigned user can mark this task as completed."))
            rec.write(
                {
                    "state": "done",
                    "completed_by": current_user.id,
                    "completed_date": fields.Datetime.now(),
                }
            )

    def action_review_completion(self):
        current_user = self.env.user
        is_manager = current_user.has_group("qlk_task_management.group_task_manager")
        for rec in self:
            if rec.state != "done":
                raise UserError(_("Only completed tasks can be reviewed."))
            if rec.create_uid != current_user and not is_manager:
                raise UserError(_("Only the task creator or manager can review completion."))
            rec.write(
                {
                    "completion_reviewed_by": current_user.id,
                    "completion_reviewed_date": fields.Datetime.now(),
                }
            )
            rec.message_post(body=_("Completion reviewed by %s.") % current_user.name)
    
    def reject_acrion(self):
        for rec in self:
            rec.state = "reject"

    def cancel_acrion(self):
        for rec in self:
            rec.state = "cancel"
