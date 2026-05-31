# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class QlkTask(models.Model):
    _inherit = "qlk.task"

    COMPLETION_STATES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    proposal_id = fields.Many2one("bd.proposal", string="Proposal", ondelete="cascade", index=True)
    engagement_id = fields.Many2one(
        "bd.engagement.letter", string="Engagement Letter", ondelete="cascade", index=True
    )
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="cascade", index=True)
    lead_id = fields.Many2one("crm.lead", string="Opportunity", ondelete="cascade", index=True)
    receive_date = fields.Datetime(string="Receive Date", tracking=True)
    delivery_date = fields.Datetime(string="Delivery Date", tracking=True)
    required_hours = fields.Float(
        string="Required Hours",
        required=True,
        tracking=True,
        digits="Product Unit of Measure",
    )
    priority = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Priority",
        default="medium",
        tracking=True,
    )
    completion_state = fields.Selection(
        selection=COMPLETION_STATES,
        string="Completion Status",
        default="draft",
        tracking=True,
    )
    completed_by = fields.Many2one("res.users", string="Completed By", readonly=True, tracking=True)
    completed_date = fields.Datetime(string="Completed On", readonly=True, tracking=True)
    completion_reviewed_by = fields.Many2one(
        "res.users", string="Completion Reviewed By", readonly=True, tracking=True
    )
    completion_reviewed_date = fields.Datetime(
        string="Completion Reviewed On", readonly=True, tracking=True
    )
    can_mark_completed = fields.Boolean(compute="_compute_completion_buttons")
    can_review_completion = fields.Boolean(compute="_compute_completion_buttons")

    @api.model
    def init(self):
        self.env.cr.execute(
            """
            UPDATE qlk_task
               SET completion_state = 'in_progress'
             WHERE completion_state IS NULL
               AND employee_id IS NOT NULL
            """
        )

    def _compute_completion_buttons(self):
        current_user = self.env.user
        is_manager = current_user.has_group("qlk_task_management.group_task_manager")
        for task in self:
            task.can_mark_completed = (
                task.completion_state == "in_progress"
                and task.assigned_user_id == current_user
            )
            task.can_review_completion = (
                task.completion_state == "completed"
                and not task.completion_reviewed_by
                and (task.create_uid == current_user or is_manager)
            )

    @api.constrains("department", "case_id", "engagement_id")
    def _check_litigation_links(self):
        for task in self:
            if task.department != "litigation":
                continue
            if not task.case_id and not task.engagement_id:
                raise ValidationError(
                    _(
                        "يجب ربط مهام التقاضي بقضية أو اتفاقية تقاضي.\n"
                        "Litigation tasks must be linked to a litigation case or engagement letter."
                    )
                )

    @api.constrains("required_hours")
    def _check_required_hours(self):
        for task in self:
            if task.required_hours <= 0:
                raise ValidationError(_("Required Hours must be strictly positive."))

    def _ensure_required_hours(self):
        missing = self.filtered(lambda task: task.required_hours <= 0)
        if missing:
            raise ValidationError(_("Required Hours must be strictly positive before saving or closing a task."))

    @api.constrains("receive_date", "delivery_date")
    def _check_receive_delivery_dates(self):
        for task in self:
            if task.receive_date and task.delivery_date and task.delivery_date < task.receive_date:
                raise ValidationError(_("Delivery Date cannot be before Receive Date."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_required_hours()
        in_progress = records.filtered(
            lambda task: task.assigned_user_id and task.completion_state in (False, "draft")
        )
        if in_progress:
            in_progress.write({"completion_state": "in_progress"})
        records._send_assignment_email()
        return records

    def write(self, vals):
        old_users = {task.id: task.assigned_user_id for task in self}
        old_completion_states = {task.id: task.completion_state for task in self}
        result = super().write(vals)
        self._ensure_required_hours()
        if "employee_id" in vals:
            for task in self:
                if task.assigned_user_id and old_users.get(task.id) != task.assigned_user_id:
                    if task.completion_state in (False, "draft"):
                        task.with_context(skip_completion_notification=True).write({"completion_state": "in_progress"})
                    task._send_assignment_email()
        if vals.get("completion_state") == "completed" and not self.env.context.get("skip_completion_notification"):
            for task in self:
                if old_completion_states.get(task.id) != "completed":
                    task._send_completion_notification()
        return result

    def action_submit_for_approval(self):
        self._ensure_required_hours()
        return super().action_submit_for_approval()

    def action_approve(self):
        self._ensure_required_hours()
        return super().action_approve()

    def _send_assignment_email(self):
        template = self.env.ref("qlk_management.mail_template_qlk_task_assignment", raise_if_not_found=False)
        if not template:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for task in self.filtered("assigned_user_id"):
            user = task.assigned_user_id
            email_to = user.partner_id.email or user.email
            if user.partner_id:
                task.message_subscribe(partner_ids=[user.partner_id.id])
                task.message_post(
                    body=_(
                        "You have been assigned a new internal task/request.<br/>"
                        "<b>Task:</b> %(name)s<br/>"
                        "<b>Priority:</b> %(priority)s<br/>"
                        "<b>Deadline:</b> %(deadline)s<br/>"
                        "<b>Created By:</b> %(creator)s<br/>"
                        "<a href='%(url)s'>Open Task</a>"
                    ) % {
                        "name": task.display_name,
                        "priority": dict(task._fields["priority"].selection).get(task.priority, task.priority or "-"),
                        "deadline": task.delivery_date or task.date_finished or "-",
                        "creator": task.create_uid.name,
                        "url": task._record_url(),
                    },
                    partner_ids=[user.partner_id.id],
                )
            if not email_to:
                continue
            # Queue the email so assignment does not block the user transaction.
            template.send_mail(
                task.id,
                force_send=False,
                email_values={"email_to": email_to},
            )
            if activity_type:
                task.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=_("New assigned task"),
                    note=_("You have been assigned to task: %s") % task.display_name,
                )

    def _record_url(self):
        self.ensure_one()
        return "%s/web#id=%s&model=%s&view_type=form" % (
            self.get_base_url(),
            self.id,
            self._name,
        )

    def _send_completion_notification(self):
        template = self.env.ref("qlk_management.mail_template_qlk_task_completion", raise_if_not_found=False)
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for task in self:
            creator = task.create_uid
            if creator.partner_id:
                task.message_subscribe(partner_ids=[creator.partner_id.id])
                task.message_post(
                    body=_("Task has been completed by %s.") % (task.completed_by.name or self.env.user.name),
                    partner_ids=[creator.partner_id.id],
                )
            email_to = creator.partner_id.email or creator.email
            if template and email_to:
                template.send_mail(task.id, force_send=False, email_values={"email_to": email_to})
            if activity_type:
                task.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=creator.id,
                    summary=_("Task completed"),
                    note=_("Task has been completed: %s") % task.display_name,
                )

    def action_mark_completed(self):
        current_user = self.env.user
        for task in self:
            if task.assigned_user_id != current_user:
                raise UserError(_("Only the assigned user can mark this task as completed."))
            if task.completion_state != "in_progress":
                raise UserError(_("Only in-progress tasks can be completed."))
            task.write(
                {
                    "completion_state": "completed",
                    "completed_by": current_user.id,
                    "completed_date": fields.Datetime.now(),
                }
            )

    def action_review_completion(self):
        current_user = self.env.user
        is_manager = current_user.has_group("qlk_task_management.group_task_manager")
        for task in self:
            if task.completion_state != "completed":
                raise UserError(_("Only completed tasks can be reviewed."))
            if task.create_uid != current_user and not is_manager:
                raise UserError(_("Only the task creator or manager can review completion."))
            task.write(
                {
                    "completion_reviewed_by": current_user.id,
                    "completion_reviewed_date": fields.Datetime.now(),
                }
            )
            task.message_post(body=_("Completion reviewed by %s.") % current_user.name)
