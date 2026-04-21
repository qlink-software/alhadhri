# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class QlkInternalRequest(models.Model):
    _name = "qlk.internal.request"
    _description = "Internal Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    STATE_SELECTION = [
        ("draft", "مسودة"),
        ("submitted", "مرسل"),
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

    def _notify_user(self, user, body):
        if user and user.partner_id:
            self.message_subscribe(partner_ids=[user.partner_id.id])
            self.message_post(body=body, partner_ids=[user.partner_id.id])
        else:
            self.message_post(body=body)

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
                    request._notify_user(
                        request.requested_by,
                        _("تم إكمال الطلب: %s") % request.display_name,
                    )
        return result

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft requests can be submitted."))
            request.state = "submitted"

    def action_start(self):
        for request in self:
            if request.state != "submitted":
                raise UserError(_("Only submitted requests can be started."))
            request.state = "in_progress"

    def action_complete(self):
        for request in self:
            if request.state != "in_progress":
                raise UserError(_("Only in-progress requests can be completed."))
            request.state = "done"

    def action_cancel(self):
        for request in self:
            if request.state == "cancelled":
                continue
            request.state = "cancelled"

    def action_reset_to_draft(self):
        for request in self:
            request.state = "draft"
