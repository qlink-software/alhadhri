# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QlkTask(models.Model):
    _inherit = "qlk.task"

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
        records._send_assignment_email()
        return records

    def write(self, vals):
        old_users = {task.id: task.assigned_user_id for task in self}
        result = super().write(vals)
        self._ensure_required_hours()
        if "employee_id" in vals:
            for task in self:
                if task.assigned_user_id and old_users.get(task.id) != task.assigned_user_id:
                    task._send_assignment_email()
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
