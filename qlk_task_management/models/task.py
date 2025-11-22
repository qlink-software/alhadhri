# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class QlkTask(models.Model):
    _name = "qlk.task"
    _description = "Task & Hours Entry"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    APPROVAL_STATES = [
        ("draft", "Draft"),
        ("waiting", "Waiting Approval"),
        ("approved", "Approved"),
        ("rejected", "Returned"),
    ]

    DEPARTMENT_SELECTION = [
        ("litigation", "Litigation"),
        ("corporate", "Corporate"),
        ("management", "Management"),
    ]

    LITIGATION_PHASE_SELECTION = [
        ("pre", "Pre-Litigation"),
        ("post", "Post-Litigation"),
    ]

    name = fields.Char(string="Task Name", required=True, tracking=True)
    description = fields.Text(string="Description")
    department = fields.Selection(
        selection=DEPARTMENT_SELECTION,
        string="Department",
        default="litigation",
        required=True,
        tracking=True,
        ondelete={
            "litigation": "set default",
            "corporate": "set default",
            "management": "set default",
        },
    )
    litigation_flow = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
        ],
        string="Proceeding Type",
        compute="_compute_litigation_flow",
        help="Mirrors the related case proceeding type when available.",
    )
    litigation_phase = fields.Selection(
        selection=LITIGATION_PHASE_SELECTION,
        string="Litigation Phase",
        tracking=True,
    )
    case_id = fields.Many2one(
        "qlk.case",
        string="Litigation Case",
        ondelete="set null",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Employee",
        required=True,
        tracking=True,
        domain="[('company_id', 'in', company_ids)]",
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Allowed Companies",
        compute="_compute_company_ids",
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned User",
        related="employee_id.user_id",
        store=True,
        readonly=True,
    )
    hours_spent = fields.Float(
        string="Hours Spent",
        required=True,
        tracking=True,
        digits="Product Unit of Measure",
    )
    date_start = fields.Date(string="Date Started", required=True, tracking=True)
    date_finished = fields.Date(string="Date Finished", tracking=True)
    approval_state = fields.Selection(
        selection=APPROVAL_STATES,
        string="Approval Status",
        default="draft",
        tracking=True,
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        tracking=True,
        help="User who should review and approve the task.",
    )
    approval_requested_on = fields.Datetime(string="Submitted On", readonly=True)
    approval_requested_by = fields.Many2one(
        "res.users",
        string="Submitted By",
        readonly=True,
    )
    approval_decision_on = fields.Datetime(string="Decision On", readonly=True)
    approver_id = fields.Many2one("res.users", string="Approved/Rejected By", readonly=True)
    approval_comment = fields.Text(string="Reviewer Comment")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_task_attachment_rel",
        "task_id",
        "attachment_id",
        string="Documents",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        required=True,
        index=True,
    )
    week_key = fields.Char(
        string="Week Key",
        compute="_compute_period_keys",
        store=True,
        help="Year-week representation (e.g. 2024-W08) used for reporting.",
    )
    month_key = fields.Char(
        string="Month Key",
        compute="_compute_period_keys",
        store=True,
        help="Year-month representation (e.g. 2024-03).",
    )
    is_reviewer = fields.Boolean(
        string="Is Reviewer",
        compute="_compute_user_flags",
        help="Indicates whether the current user is the assigned reviewer.",
    )
    can_approve = fields.Boolean(
        string="Can Approve",
        compute="_compute_user_flags",
    )
    can_submit = fields.Boolean(
        string="Can Submit",
        compute="_compute_user_flags",
    )

    @api.depends("employee_id")
    def _compute_company_ids(self):
        for task in self:
            companies = task.env.company
            employee = task.employee_id
            if employee:
                companies |= employee.company_id
                if "company_ids" in employee._fields:
                    companies |= employee.company_ids
            task.company_ids = companies

    @api.depends("date_start")
    def _compute_period_keys(self):
        for task in self:
            if task.date_start:
                as_date = fields.Date.to_date(task.date_start)
                week_number = as_date.isocalendar()[1]
                task.week_key = f"{as_date.year}-W{week_number:02d}"
                task.month_key = f"{as_date.year}-{as_date.month:02d}"
            else:
                task.week_key = False
                task.month_key = False

    @api.depends("approval_state", "reviewer_id", "employee_id")
    def _compute_user_flags(self):
        current_user = self.env.user
        for task in self:
            task.is_reviewer = bool(task.reviewer_id and task.reviewer_id == current_user)
            can_approve = task.approval_state == "waiting" and (
                task.is_reviewer
                or current_user.has_group("qlk_law.group_qlk_law_manager")
            )
            task.can_approve = can_approve
            task.can_submit = task.approval_state in ("draft", "rejected") and (
                current_user == task.assigned_user_id
                or current_user == task.create_uid
                or current_user.has_group("qlk_law.group_qlk_law_manager")
            )

    @api.constrains("hours_spent")
    def _check_hours_positive(self):
        for task in self:
            if task.hours_spent <= 0:
                raise ValidationError(_("Hours Spent must be strictly positive."))

    @api.depends("case_id")
    def _compute_litigation_flow(self):
        for task in self:
            if task.case_id and "litigation_flow" in task.case_id._fields:
                task.litigation_flow = task.case_id.litigation_flow
            else:
                task.litigation_flow = False

    @api.constrains("date_start", "date_finished")
    def _check_dates(self):
        for task in self:
            if task.date_start and task.date_finished and task.date_finished < task.date_start:
                raise ValidationError(_("Date Finished cannot be before Date Started."))

    @api.constrains("department", "case_id", "litigation_phase")
    def _check_department_links(self):
        for task in self:
            if task.department == "litigation":
                if not task.case_id:
                    raise ValidationError(_("Litigation tasks must be linked to a litigation case."))
                if not task.litigation_phase:
                    raise ValidationError(_("Litigation tasks must specify whether they are Pre-Litigation or Post-Litigation."))
            elif task.department == "management" and task.case_id:
                raise ValidationError(_("Management tasks cannot be linked to a litigation case."))

    @api.onchange("department")
    def _onchange_department(self):
        if self.department != "litigation":
            self.litigation_phase = False
            self.case_id = False

    def action_open_related_record(self):
        self.ensure_one()
        if self.department == "litigation" and self.case_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "qlk.case",
                "view_mode": "form",
                "res_id": self.case_id.id,
                "target": "current",
            }
        if self.department == "management" and self.employee_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "hr.employee",
                "view_mode": "form",
                "res_id": self.employee_id.id,
                "target": "current",
            }
        return False

    def action_submit_for_approval(self):
        for task in self:
            if task.approval_state not in ("draft", "rejected"):
                raise UserError(_("Only draft or returned tasks can be submitted for approval."))
            if not task.reviewer_id:
                raise UserError(_("Please select a reviewer before submitting for approval."))
            task.write(
                {
                    "approval_state": "waiting",
                    "approval_requested_on": fields.Datetime.now(),
                    "approval_requested_by": self.env.user.id,
                    "approval_comment": False if task.approval_state == "rejected" else task.approval_comment,
                }
            )
            task.message_post(
                body=_("Task submitted for approval and awaiting reviewer response."),
                partner_ids=[task.reviewer_id.partner_id.id] if task.reviewer_id and task.reviewer_id.partner_id else False,
            )

    def action_mark_draft(self):
        for task in self:
            task.write(
                {
                    "approval_state": "draft",
                    "approval_requested_on": False,
                    "approval_decision_on": False,
                    "approver_id": False,
                }
            )

    def action_approve(self):
        current_user = self.env.user
        for task in self:
            if task.approval_state != "waiting":
                raise UserError(_("Only tasks waiting for approval can be approved."))
            if not (
                current_user == task.reviewer_id
                or current_user.has_group("qlk_law.group_qlk_law_manager")
            ):
                raise UserError(_("You are not permitted to approve this task."))
            task.write(
                {
                    "approval_state": "approved",
                    "approval_decision_on": fields.Datetime.now(),
                    "approver_id": current_user.id,
                }
            )
            partners = []
            if task.assigned_user_id and task.assigned_user_id.partner_id:
                partners.append(task.assigned_user_id.partner_id.id)
            if task.reviewer_id and task.reviewer_id.partner_id and task.reviewer_id.partner_id.id not in partners:
                partners.append(task.reviewer_id.partner_id.id)
            if partners:
                task.message_post(
                    body=_("Task approved."),
                    partner_ids=partners,
                )

    def action_reject(self, reason=None):
        current_user = self.env.user
        for task in self:
            if task.approval_state != "waiting":
                raise UserError(_("Only tasks waiting for approval can be rejected."))
            if not (
                current_user == task.reviewer_id
                or current_user.has_group("qlk_law.group_qlk_law_manager")
            ):
                raise UserError(_("You are not permitted to reject this task."))
            comment = reason or task.approval_comment
            if not comment:
                raise UserError(_("Please provide a comment when rejecting a task."))
            task.write(
                {
                    "approval_state": "rejected",
                    "approval_decision_on": fields.Datetime.now(),
                    "approver_id": current_user.id,
                    "approval_comment": comment,
                }
            )
            partners = []
            if task.assigned_user_id and task.assigned_user_id.partner_id:
                partners.append(task.assigned_user_id.partner_id.id)
            if task.reviewer_id and task.reviewer_id.partner_id and task.reviewer_id.partner_id.id not in partners:
                partners.append(task.reviewer_id.partner_id.id)
            body = _("Task rejected: %s") % comment
            task.message_post(
                body=body,
                partner_ids=partners,
            )

    def unlink(self):
        for task in self:
            if task.approval_state == "approved" and not self.env.user.has_group("qlk_law.group_qlk_law_manager"):
                raise UserError(_("Only managers can delete approved tasks."))
        return super().unlink()

    @api.model
    def summarize_hours(self, date_from=None, date_to=None, employee_ids=None):
        """Helper to aggregate approved hours for reporting."""
        domain = [("approval_state", "=", "approved")]
        if date_from:
            domain.append(("date_start", ">=", date_from))
        if date_to:
            domain.append(("date_start", "<=", date_to))
        if employee_ids:
            domain.append(("employee_id", "in", employee_ids))
        result = self.read_group(domain, ["hours_spent"], ["employee_id"])
        return {
            entry["employee_id"][0]: entry["hours_spent"]
            for entry in result
            if entry.get("employee_id")
        }
