# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrResignationRequest(models.Model):
    _name = "hr.resignation.request"
    _description = "Employee Resignation Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        tracking=True,
        default=lambda self: self._default_employee_id(),
        index=True,
    )
    resignation_date = fields.Date(
        string="Resignation Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    reason = fields.Text(string="Reason", required=True, tracking=True)
    notice_period_days = fields.Integer(
        string="Notice Period Days",
        default=15,
        tracking=True,
    )
    approval_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval State",
        default="draft",
        tracking=True,
        copy=False,
    )
    manager_id = fields.Many2one(
        "res.users",
        string="Manager",
        tracking=True,
        default=lambda self: self._default_manager_id(),
    )
    rejection_reason = fields.Text(string="Rejection Reason", tracking=True, copy=False)
    approval_date = fields.Date(string="Approval Date", tracking=True, copy=False)
    effective_date = fields.Date(
        string="Effective Date",
        compute="_compute_effective_date",
        store=True,
        tracking=True,
    )
    can_current_user_approve = fields.Boolean(compute="_compute_can_current_user_approve")
    is_current_user_employee = fields.Boolean(compute="_compute_is_current_user_employee")

    @api.model
    def _default_employee_id(self):
        employee = self.env.user.employee_id
        if not employee and self.env.user.employee_ids:
            employee = self.env.user.employee_ids[:1]
        return employee.id if employee else False

    @api.model
    def _default_manager_id(self):
        employee = self.env.user.employee_id
        manager = employee.parent_id.user_id if employee and employee.parent_id else False
        return manager.id if manager else False

    @api.depends("approval_state", "approval_date", "notice_period_days")
    def _compute_effective_date(self):
        for request in self:
            if request.approval_state == "approved" and request.approval_date:
                request.effective_date = request.approval_date + timedelta(days=request.notice_period_days or 15)
            else:
                request.effective_date = False

    def _current_user_can_approve(self):
        self.ensure_one()
        user = self.env.user
        if self.manager_id == user:
            return True
        return bool(
            user.has_group("hr.group_hr_manager")
            or user.has_group("qlk_management.group_mp")
        )

    @api.depends("manager_id")
    def _compute_can_current_user_approve(self):
        for request in self:
            request.can_current_user_approve = request._current_user_can_approve()

    @api.depends("employee_id")
    def _compute_is_current_user_employee(self):
        current_employee = self.env.user.employee_id
        for request in self:
            request.is_current_user_employee = bool(
                current_employee and request.employee_id == current_employee
            )

    @api.constrains("notice_period_days")
    def _check_notice_period_days(self):
        for request in self:
            if request.notice_period_days < 1:
                raise ValidationError(_("Notice period days must be at least 1 day."))

    @api.constrains("employee_id", "approval_state")
    def _check_single_active_request(self):
        active_states = ("draft", "submitted", "approved")
        for request in self:
            if not request.employee_id or request.approval_state not in active_states:
                continue
            duplicate = self.search_count(
                [
                    ("id", "!=", request.id),
                    ("employee_id", "=", request.employee_id.id),
                    ("approval_state", "in", active_states),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("Only one active resignation request is allowed per employee.")
                )

    def _check_employee_ownership(self):
        self.ensure_one()
        employee = self.env.user.employee_id
        if not employee or self.employee_id != employee:
            raise UserError(_("You can only submit resignation requests for your own employee record."))

    def _check_approval_rights(self):
        self.ensure_one()
        if not self._current_user_can_approve():
            raise UserError(_("Only the assigned manager or HR manager can approve or reject this resignation request."))

    def _notify_employee(self, message, title):
        self.ensure_one()
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_warning(message, title=title, sticky=True)

    def action_submit_resignation(self):
        for request in self:
            if request.approval_state != "draft":
                raise UserError(_("Only draft resignation requests can be submitted."))
            request._check_employee_ownership()
            manager = request.manager_id or request.employee_id.parent_id.user_id
            if not manager:
                raise UserError(_("Please assign a manager before submitting the resignation request."))
            request.write(
                {
                    "approval_state": "submitted",
                    "manager_id": manager.id,
                    "rejection_reason": False,
                }
            )
            request.employee_id.message_post(body=_("Resignation request submitted."))
            request.message_post(
                body=_("Resignation submitted for approval."),
                subject=_("Resignation Submission"),
            )
        return True

    def action_approve(self):
        today = fields.Date.context_today(self)
        for request in self:
            if request.approval_state != "submitted":
                raise UserError(_("Only submitted resignation requests can be approved."))
            request._check_approval_rights()
            effective_date = today + timedelta(days=request.notice_period_days or 15)
            request.write(
                {
                    "approval_state": "approved",
                    "approval_date": today,
                    "manager_id": self.env.user.id,
                    "rejection_reason": False,
                }
            )
            request.employee_id.sudo().write(
                {
                    "resignation_approved": True,
                    "resignation_date": request.resignation_date,
                    "approval_date": today,
                    "effective_date": effective_date,
                    "user_deactivated_after_notice": False,
                }
            )
            approval_message = _(
                "Resignation approved. Access will be revoked after %s days."
            ) % (request.notice_period_days or 15)
            request.employee_id.message_post(body=approval_message)
            request.message_post(body=approval_message, subject=_("Resignation Approved"))
            request._notify_employee(
                _("Your resignation request has been approved. Access ends on %s.")
                % fields.Date.to_string(effective_date),
                _("Resignation Approved"),
            )
        return True

    def action_open_reject_wizard(self):
        self.ensure_one()
        self._check_approval_rights()
        if self.approval_state != "submitted":
            raise UserError(_("Only submitted resignation requests can be rejected."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Resignation"),
            "res_model": "qlk.hr.resignation.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_reject_with_reason(self, reason):
        self.ensure_one()
        self._check_approval_rights()
        if self.approval_state != "submitted":
            raise UserError(_("Only submitted resignation requests can be rejected."))
        if not reason:
            raise UserError(_("A rejection reason is required."))
        self.write(
            {
                "approval_state": "rejected",
                "manager_id": self.env.user.id,
                "rejection_reason": reason,
                "approval_date": False,
            }
        )
        rejection_message = _("Resignation rejected: %s") % reason
        self.employee_id.message_post(body=rejection_message)
        self.message_post(body=rejection_message, subject=_("Resignation Rejected"))
        self._notify_employee(
            _("Your resignation request has been rejected: %s") % reason,
            _("Resignation Rejected"),
        )
        return True
