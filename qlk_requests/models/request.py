# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


class QlkInternalRequest(models.Model):
    _name = "qlk.internal.request"
    _description = "Internal Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    STATE_SELECTION = [
        ("draft", "مسودة"),
        ("in_progress", "قيد التنفيذ"),
        ("done", "مكتمل"),
        ("cancelled", "ملغي"),
    ]

    PRIORITY_SELECTION = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    name = fields.Char(string="اسم الطلب", required=True, tracking=True)
    description = fields.Text(string="وصف الطلب", tracking=True)
    request_date = fields.Date(
        string="تاريخ الطلب",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    requested_by = fields.Many2one(
        "res.users",
        string="الطالب",
        default=lambda self: self.env.user,
        required=True,
        index=True,
        tracking=True,
    )
    assigned_to = fields.Many2one(
        "res.users",
        string="المطلوب منه",
        index=True,
        tracking=True,
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        "qlk_internal_request_employee_rel",
        "request_id",
        "employee_id",
        string="الموظفون المعنيون",
        tracking=True,
    )
    assigned_user_ids = fields.Many2many(
        "res.users",
        string="Assigned Users",
        compute="_compute_assigned_user_ids",
        store=True,
        compute_sudo=True,
    )
    receive_date = fields.Datetime(string="تاريخ الاستلام", tracking=True)
    delivery_date = fields.Datetime(string="تاريخ التسليم", tracking=True)
    required_hours = fields.Float(
        string="الساعات المطلوبة",
        digits="Product Unit of Measure",
        tracking=True,
    )
    engagement_id = fields.Many2one(
        "bd.engagement.letter",
        string="الاتفاقية",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    case_id = fields.Many2one(
        "qlk.case",
        string="الدعوى",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    hours_spent = fields.Float(
        string="الساعات",
        digits="Product Unit of Measure",
        tracking=True,
    )
    completion_notes = fields.Text(string="ملاحظات الإنجاز", tracking=True)
    completed_by = fields.Many2one("res.users", string="الموظف المنفذ", readonly=True, tracking=True)
    done_date = fields.Datetime(string="تاريخ الانتهاء", readonly=True, tracking=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_internal_request_attachment_rel",
        "request_id",
        "attachment_id",
        string="المرفقات",
    )
    state = fields.Selection(
        selection=STATE_SELECTION,
        string="الحالة",
        default="draft",
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        selection=PRIORITY_SELECTION,
        string="Priority",
        default="medium",
        tracking=True,
    )

    @api.model
    def init(self):
        # Keep upgrades safe for databases that still contain the former submitted state.
        self.env.cr.execute(
            "UPDATE qlk_internal_request SET state = 'in_progress' WHERE state = 'submitted'"
        )

    @api.depends("assigned_to", "employee_ids.user_id")
    def _compute_assigned_user_ids(self):
        for request in self:
            users = request.employee_ids.mapped("user_id")
            if request.assigned_to:
                users |= request.assigned_to
            request.assigned_user_ids = [Command.set(users.ids)]

    @api.onchange("engagement_id")
    def _onchange_engagement_id(self):
        for request in self:
            if request.engagement_id and request.case_id and request.case_id.engagement_id != request.engagement_id:
                request.case_id = False

    @api.onchange("case_id")
    def _onchange_case_id(self):
        for request in self:
            if request.case_id and request.case_id.engagement_id:
                request.engagement_id = request.case_id.engagement_id.id

    @api.constrains("hours_spent")
    def _check_hours_spent(self):
        for request in self:
            if request.hours_spent < 0:
                raise ValidationError(_("Hours cannot be negative."))

    @api.constrains("required_hours")
    def _check_required_hours(self):
        for request in self:
            if request.required_hours < 0:
                raise ValidationError(_("Required Hours cannot be negative."))

    @api.constrains("receive_date", "delivery_date")
    def _check_receive_delivery_dates(self):
        for request in self:
            if request.receive_date and request.delivery_date and request.delivery_date < request.receive_date:
                raise ValidationError(_("Delivery Date cannot be before Receive Date."))

    @api.constrains("engagement_id", "case_id")
    def _check_project_case_consistency(self):
        for request in self:
            if (
                request.engagement_id
                and request.case_id
                and request.case_id.engagement_id
                and request.case_id.engagement_id != request.engagement_id
            ):
                raise ValidationError(_("The selected case must belong to the selected engagement letter."))

    def _notify_user(self, user, body):
        if user and user.partner_id:
            self.message_subscribe(partner_ids=[user.partner_id.id])
            self.message_post(body=body, partner_ids=[user.partner_id.id])
        else:
            self.message_post(body=body)

    def _send_template_to_users(self, template_xmlid, users):
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template or not users:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for request in self:
            for user in users.filtered(lambda item: item.active and (item.partner_id.email or item.email)):
                template.send_mail(
                    request.id,
                    force_send=False,
                    email_values={"email_to": user.partner_id.email or user.email},
                )
                if activity_type:
                    request.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=_("Internal request notification"),
                        note=_("Please review request: %s") % request.display_name,
                    )

    def _get_mp_users(self):
        Employee = self.env["hr.employee"].sudo()
        mp_employees = Employee.search([("is_mp", "=", True), ("user_id", "!=", False)])
        users = mp_employees.mapped("user_id")
        for xmlid in (
            "qlk_management.group_pre_litigation_manager",
            "qlk_requests.group_request_manager",
        ):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                users |= group.users
        return users.filtered(lambda user: user.active)

    def _send_created_to_mp_email(self):
        for request in self:
            request._send_template_to_users(
                "qlk_requests.mail_template_internal_request_created_mp",
                request._get_mp_users(),
            )

    def _send_done_to_creator_email(self):
        for request in self.filtered("requested_by"):
            request._send_template_to_users(
                "qlk_requests.mail_template_internal_request_done_creator",
                request.requested_by,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("requested_by", self.env.user.id)
            vals.setdefault("state", "draft")
        records = super().create(vals_list)
        for record in records.filtered("assigned_to"):
            record._notify_user(
                record.assigned_to,
                _("تم إسناد طلب جديد إليك: %s") % record.display_name,
            )
        records._send_created_to_mp_email()
        return records

    def write(self, vals):
        old_assignees = {request.id: request.assigned_to for request in self}
        old_states = {request.id: request.state for request in self}
        result = super().write(vals)
        if "assigned_to" in vals:
            for request in self.filtered("assigned_to"):
                if old_assignees.get(request.id) != request.assigned_to:
                    request._notify_user(
                        request.assigned_to,
                        _("تم إسناد الطلب إليك: %s") % request.display_name,
                    )
        if vals.get("state") == "done":
            for request in self:
                if old_states.get(request.id) != "done":
                    if not request.done_date:
                        request.done_date = fields.Datetime.now()
                    if not request.completed_by:
                        request.completed_by = self.env.user
                    request._notify_user(
                        request.requested_by,
                        _("تم إكمال الطلب: %s") % request.display_name,
                    )
                    request._send_done_to_creator_email()
        return result

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft requests can be submitted."))
            request.state = "in_progress"

    def action_start(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft requests can be started."))
            request.state = "in_progress"

    def action_complete(self):
        for request in self:
            if request.state != "in_progress":
                raise UserError(_("Only in-progress requests can be completed."))
            request.write(
                {
                    "state": "done",
                    "done_date": fields.Datetime.now(),
                    "completed_by": self.env.user.id,
                }
            )

    def action_cancel(self):
        for request in self:
            if request.state == "cancelled":
                continue
            request.state = "cancelled"

    def action_reset_to_draft(self):
        for request in self:
            request.state = "draft"
