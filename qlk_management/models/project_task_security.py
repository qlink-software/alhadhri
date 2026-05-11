# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES
from odoo.exceptions import ValidationError
from odoo.fields import Command


class ProjectTask(models.Model):
    _inherit = "project.task"

    receive_date = fields.Datetime(string="Receive Date", tracking=True)
    delivery_date = fields.Datetime(string="Delivery Date", tracking=True)
    required_hours = fields.Float(
        string="Required Hours",
        required=True,
        default=0.0,
        tracking=True,
        digits="Product Unit of Measure",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "project_task_ir_attachments_rel",
        "task_id",
        "attachment_id",
        string="Attachments",
    )
    case_id = fields.Many2one(
        "qlk.case",
        string="Litigation Case",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    qlk_project_id = fields.Many2one(
        "qlk.project",
        string="Legal Project",
        related="case_id.project_id",
        store=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Primary Assignee",
        compute="_compute_primary_user_id",
        inverse="_inverse_primary_user_id",
        store=True,
        index=True,
        help="Stored primary assignee used by strict lawyer record rules.",
    )

    @api.depends("user_ids")
    def _compute_primary_user_id(self):
        # Odoo 18 uses user_ids; this alias keeps security domains simple and indexed.
        for task in self:
            task.user_id = task.user_ids[:1] if task.user_ids else False

    def _inverse_primary_user_id(self):
        for task in self:
            task.user_ids = [Command.set([task.user_id.id])] if task.user_id else [Command.clear()]

    def init(self):
        # Existing databases may already contain project tasks before this required field exists.
        self.env.cr.execute("UPDATE project_task SET required_hours = 0 WHERE required_hours IS NULL")

    @api.onchange("case_id")
    def _onchange_case_id(self):
        for task in self:
            case = task.case_id
            if case and case.client_id and not task.partner_id:
                task.partner_id = case.client_id.id
            if case and case.project_id and not task.project_id:
                task.project_id = case.project_id._get_or_create_timesheet_project().id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_legal_case_defaults(vals)
            if vals.get("case_id") and not vals.get("user_ids"):
                case = self.env["qlk.case"].browse(vals["case_id"])
                if case.exists() and case.employee_id.user_id:
                    vals["user_ids"] = [Command.set([case.employee_id.user_id.id])]
        tasks = super().create(vals_list)
        tasks._ensure_required_hours()
        for task in tasks.filtered("user_ids"):
            task._send_assignment_email(task.user_ids)
        return tasks

    def write(self, vals):
        old_assignees = {task.id: set(task.user_ids.ids) for task in self}
        vals = dict(vals)
        if vals.get("case_id") and not vals.get("project_id"):
            self._apply_legal_case_defaults(vals)
        self._check_required_hours_before_closing(vals)
        result = super().write(vals)
        self._ensure_required_hours()
        if "user_id" in vals or "user_ids" in vals:
            for task in self:
                new_users = task.user_ids.filtered(lambda user: user.id not in old_assignees.get(task.id, set()))
                if new_users:
                    task._send_assignment_email(new_users)
        return result

    def _apply_legal_case_defaults(self, vals):
        case_id = vals.get("case_id")
        if not case_id:
            return vals
        case = self.env["qlk.case"].browse(case_id)
        if not case.exists():
            return vals
        if case.client_id and not vals.get("partner_id"):
            vals["partner_id"] = case.client_id.id
        legal_project = case.project_id
        if legal_project and not vals.get("project_id"):
            vals["project_id"] = legal_project._get_or_create_timesheet_project().id
        return vals

    @api.constrains("case_id")
    def _check_case_required_for_legal_task(self):
        if not self.env.context.get("qlk_require_case_id"):
            return
        for task in self:
            if not task.case_id:
                raise ValidationError(_("Tasks created from legal cases must be linked to a case."))

    @api.constrains("required_hours")
    def _check_required_hours(self):
        for task in self:
            if task.required_hours <= 0:
                raise ValidationError(_("Required Hours must be strictly positive."))

    def _ensure_required_hours(self):
        missing = self.filtered(lambda task: task.required_hours <= 0)
        if missing:
            raise ValidationError(_("Required Hours must be strictly positive before saving or closing a task."))

    def _check_required_hours_before_closing(self, vals):
        closing_state = vals.get("state") in CLOSED_STATES
        closing_stage = False
        if vals.get("stage_id"):
            closing_stage = bool(self.env["project.task.type"].browse(vals["stage_id"]).fold)
        if not closing_state and not closing_stage:
            return
        missing = self.filtered(lambda task: vals.get("required_hours", task.required_hours) <= 0)
        if missing:
            raise ValidationError(_("Required Hours must be entered before moving the task to Done."))

    @api.constrains("receive_date", "delivery_date")
    def _check_receive_delivery_dates(self):
        for task in self:
            if task.receive_date and task.delivery_date and task.delivery_date < task.receive_date:
                raise ValidationError(_("Delivery Date cannot be before Receive Date."))

    def _send_assignment_email(self, users=None):
        template = self.env.ref("qlk_management.mail_template_project_task_assignment", raise_if_not_found=False)
        if not template:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for task in self:
            recipients = users or task.user_ids
            for user in recipients.filtered(lambda item: item.active and (item.partner_id.email or item.email)):
                # Queue emails to avoid delaying task create/write transactions.
                template.send_mail(
                    task.id,
                    force_send=False,
                    email_values={"email_to": user.partner_id.email or user.email},
                )
                if activity_type:
                    task.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=_("New assigned task"),
                        note=_("You have been assigned to task: %s") % task.display_name,
                    )
