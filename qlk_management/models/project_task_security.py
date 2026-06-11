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

    @api.model
    def _normalize_assignee_vals(self, vals):
        """Keep kanban/default single-assignee values aligned with Odoo 18 user_ids."""
        if "user_ids" in vals or "user_id" not in vals:
            return vals
        vals["user_ids"] = [Command.set([vals["user_id"]])] if vals.get("user_id") else [Command.clear()]
        return vals

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        default_user_id = self.env.context.get("default_user_id")
        if default_user_id and "user_ids" in fields_list and not vals.get("user_ids"):
            vals["user_ids"] = [Command.set([default_user_id])]
        return vals

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
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            self._normalize_assignee_vals(vals)
            self._apply_legal_case_defaults(vals)
            self._ensure_allocated_hours_in_vals(vals)
            if vals.get("case_id") and not vals.get("user_ids"):
                case = self.env["qlk.case"].browse(vals["case_id"])
                if case.exists() and case.employee_id.user_id:
                    vals["user_ids"] = [Command.set([case.employee_id.user_id.id])]
        tasks = super().create(vals_list)
        for task in tasks.filtered("user_ids"):
            task._send_assignment_email(task.user_ids)
        return tasks

    def write(self, vals):
        old_assignees = {task.id: set(task.user_ids.ids) for task in self}
        vals = dict(vals)
        self._normalize_assignee_vals(vals)
        if vals.get("case_id") and not vals.get("project_id"):
            self._apply_legal_case_defaults(vals)
        self._check_required_hours_before_closing(vals)
        self._ensure_allocated_hours_for_write(vals)
        result = super().write(vals)
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

    @api.constrains("allocated_hours")
    def _check_allocated_hours(self):
        for task in self:
            if task.allocated_hours <= 0:
                raise ValidationError(_("Allocated Time must be entered before saving the task."))

    def _ensure_allocated_hours_in_vals(self, vals):
        allocated_hours = vals.get("allocated_hours", self.env.context.get("default_allocated_hours", 0.0)) or 0.0
        if allocated_hours <= 0:
            raise ValidationError(_("Allocated Time must be entered before saving the task."))

    def _ensure_allocated_hours_for_write(self, vals):
        if "allocated_hours" in vals:
            allocated_hours = vals.get("allocated_hours") or 0.0
            missing = self if allocated_hours <= 0 else self.env["project.task"]
        else:
            missing = self.filtered(lambda task: task.allocated_hours <= 0)
        if missing:
            raise ValidationError(_("Allocated Time must be entered before saving the task."))

    def _check_required_hours_before_closing(self, vals):
        closing_state = vals.get("state") in CLOSED_STATES
        closing_stage = False
        if vals.get("stage_id"):
            closing_stage = bool(self.env["project.task.type"].browse(vals["stage_id"]).fold)
        if not closing_state and not closing_stage:
            return
        missing = self.filtered(lambda task: vals.get("allocated_hours", task.allocated_hours) <= 0)
        if missing:
            raise ValidationError(_("Allocated Time must be entered before moving the task to Done."))

    def _send_assignment_email(self, users=None):
        template = self.env.ref("qlk_management.mail_template_project_task_assignment", raise_if_not_found=False)
        if not template:
            return
        for task in self:
            recipients = users or task.user_ids
            partners = recipients.filtered(lambda item: item.active and (item.partner_id.email or item.email)).mapped(
                "partner_id"
            )
            if not partners:
                continue
            message = task.message_post_with_source(
                template.sudo(),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            for partner in partners:
                mail_values = task._notify_by_email_get_base_mail_values(
                    message,
                    additional_values={
                        "auto_delete": False,
                        "body_html": message.body,
                    },
                )
                mail_values = task._notify_by_email_get_final_mail_values([partner.id], mail_values)
                mail = self.env["mail.mail"].sudo().create(mail_values)
                notification_values = {
                    "author_id": message.author_id.id,
                    "is_read": True,
                    "mail_mail_id": mail.id,
                    "mail_message_id": message.id,
                    "notification_status": "ready",
                    "notification_type": "email",
                    "res_partner_id": partner.id,
                }
                notification = self.env["mail.notification"].sudo().search(
                    [
                        ("mail_message_id", "=", message.id),
                        ("res_partner_id", "=", partner.id),
                    ],
                    limit=1,
                )
                if notification:
                    notification.write(notification_values)
                else:
                    self.env["mail.notification"].sudo().create(notification_values)
                mail.sudo().send(raise_exception=False)
