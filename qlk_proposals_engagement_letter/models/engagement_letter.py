# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class EngagementLetter(models.Model):
    _name = "qlk.engagement.letter"
    _description = "Engagement Letter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    CONTRACT_SELECTION = [
        ("retainer", "Retainer Contract"),
        ("lump_sum", "Lump Sum Agreement"),
    ]

    RETAINER_SCOPE_SELECTION = [
        ("corporate", "Corporate Services"),
        ("litigation", "Litigation Services"),
        ("both", "Corporate & Litigation"),
    ]

    DEPARTMENT_SELECTION = [
        ("C", "Corporate"),
        ("L", "Litigation"),
        ("CL", "Combined Litigation & Corporate"),
        ("A", "Arbitration"),
    ]

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_SELECTION = [
        ("paid", "Paid"),
        ("pro_bono", "Pro Bono"),
    ]

    APPROVAL_STATE_SELECTION = [
        ("draft", "In Preparation"),
        ("waiting", "Waiting Approval"),
        ("approved", "Approved"),
        ("rejected", "Returned"),
    ]

    name = fields.Char(default="New", copy=False, tracking=True, readonly=True)
    reference = fields.Char(copy=False, tracking=True, readonly=True, required=True)
    serial_number = fields.Integer(string="Serial Number", readonly=True, copy=False)
    year = fields.Integer(string="Year", compute="_compute_year", store=True)
    date = fields.Date(default=lambda self: fields.Date.context_today(self), tracking=True, required=True)
    state = fields.Selection(selection=STATE_SELECTION, default="draft", tracking=True)
    approval_state = fields.Selection(
        selection=APPROVAL_STATE_SELECTION,
        default="draft",
        tracking=True,
        string="Approval Status",
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requester",
        default=lambda self: self.env.user,
        readonly=True,
    )
    approver_id = fields.Many2one("res.users", string="Approver", tracking=True)
    approval_requested_on = fields.Datetime(string="Submitted On", readonly=True)
    approval_decision_on = fields.Datetime(string="Decision On", readonly=True)
    approval_comment = fields.Text(string="Approval Comment")
    rejection_reason = fields.Text(string="Rejection Reason")
    signed_document = fields.Binary(string="Signed Engagement Letter", attachment=True)
    signed_document_filename = fields.Char()
    signed_document_uploaded_on = fields.Datetime(string="Signed Document Uploaded On", readonly=True)
    signed_document_uploaded_by = fields.Many2one("res.users", string="Uploaded By", readonly=True)
    can_print = fields.Boolean(string="Can Print", compute="_compute_can_print")
    client_unique_code = fields.Char(string="Client Unique Code", readonly=True, copy=False, tracking=True)

    contract_type = fields.Selection(selection=CONTRACT_SELECTION, required=True, default="retainer", tracking=True)
    retainer_scope = fields.Selection(selection=RETAINER_SCOPE_SELECTION, tracking=True)
    department_type = fields.Selection(selection=DEPARTMENT_SELECTION, required=True, default="C", tracking=True)
    payment_type = fields.Selection(
        selection=PAYMENT_SELECTION,
        default="paid",
        required=True,
        tracking=True,
    )
    proposal_id = fields.Many2one(
        "qlk.business.proposal",
        string="Business Proposal",
        readonly=True,
        copy=False,
    )
    legacy_proposal_id = fields.Many2one(
        "qlk.engagement.proposal",
        string="Legacy Engagement Proposal",
        readonly=True,
        copy=False,
    )
    employee_id = fields.Many2one("hr.employee", string="Responsible Lawyer", tracking=True)
    cost_calculation_id = fields.Many2one(
        "cost.calculation",
        string="Cost Calculation",
        ondelete="set null",
    )
    cost_base_amount = fields.Float(
        string="Base Cost",
        compute="_compute_cost_amounts",
        store=True,
        readonly=True,
    )
    cost_additional_amount = fields.Float(string="Additional Cost (Cost Calc)", default=0.0, tracking=True)
    cost_total_amount = fields.Float(
        string="Total Cost",
        compute="_compute_cost_amounts",
        store=True,
        readonly=True,
    )
    is_approved = fields.Boolean(string="Project Approved", tracking=True, default=False)
    approval_user_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    approval_date = fields.Datetime(string="Approval Date", readonly=True, copy=False)
    project_id = fields.Many2one("qlk.project", string="Project", readonly=True, copy=False)
    estimated_hours = fields.Float(string="Estimated Hours", tracking=True)
    hourly_rate = fields.Monetary(string="Hourly Rate", tracking=True)
    additional_cost = fields.Monetary(string="Additional Costs", tracking=True)
    estimated_total = fields.Monetary(
        string="Estimated Total",
        compute="_compute_estimated_total",
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Office",
        required=True,
        default=lambda self: self.env.company.id,
        index=True,
    )
    office_name = fields.Char(related="company_id.name", string="Office Name", readonly=True)
    office_license_number = fields.Char(
        related="company_id.engagement_license_number",
        string="License Number",
        readonly=True,
    )
    office_location = fields.Char(
        related="company_id.engagement_office_location",
        string="Office Location",
        readonly=True,
    )
    office_email = fields.Char(
        related="company_id.engagement_office_email",
        string="Office Email",
        readonly=True,
    )
    office_phone = fields.Char(
        related="company_id.engagement_office_phone",
        string="Office Phone",
        readonly=True,
    )
    office_authorized_signatory_name = fields.Char(
        related="company_id.engagement_authorized_signatory_name",
        string="Authorized Signatory",
        readonly=True,
    )
    office_authorized_signatory_title = fields.Char(
        related="company_id.engagement_authorized_signatory_title",
        string="Signatory Title",
        readonly=True,
    )
    office_authorized_signatory_details = fields.Text(
        related="company_id.engagement_authorized_signatory_details",
        string="Signatory Details",
        readonly=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        tracking=True,
        domain="[('parent_id', '=', False)]",
    )
    client_capacity = fields.Char(string="Client Capacity/Title")
    client_document_ids = fields.One2many(
        related="partner_id.client_document_ids",
        string="Client Documents",
        readonly=True,
    )
    client_document_warning = fields.Html(
        related="partner_id.document_warning_message",
        string="Document Warning",
        readonly=True,
    )
    client_type = fields.Selection(
        selection=[("individual", "Individual Client"), ("company", "Company Client")],
        string="Client Type",
        default="individual",
        required=True,
        tracking=True,
    )

    # Individual client details
    individual_full_name = fields.Char(string="Full Name")
    individual_qid = fields.Char(string="Qatar ID")
    individual_passport = fields.Char(string="Passport Number")
    individual_email = fields.Char(string="Email")
    individual_phone = fields.Char(string="Phone")
    individual_authorized_signatory_name = fields.Char(string="Authorized Signatory Name")
    individual_authorized_signatory_details = fields.Char(string="Authorized Signatory Details")

    # Company client details
    company_name = fields.Char(string="Company Name")
    company_cr_number = fields.Char(string="CR Number")
    company_location = fields.Char(string="Company Location")
    company_email = fields.Char(string="Company Email")
    company_phone = fields.Char(string="Company Phone")
    company_authorized_signatory_name = fields.Char(string="Authorized Signatory Name")
    company_authorized_signatory_id_number = fields.Char(string="Signatory ID Number")
    company_authorized_signatory_nationality = fields.Char(string="Signatory Nationality")
    company_authorized_signatory_title = fields.Char(string="Signatory Title")

    client_detail_ids = fields.One2many(
        "qlk.engagement.client.detail",
        "engagement_id",
        string="Client Contacts",
    )

    scope_of_work = fields.Html(string="Scope of Work", sanitize=False)
    total_fees = fields.Monetary(string="Total Legal Fees")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )
    installment_ids = fields.One2many("qlk.engagement.installment", "engagement_id", string="Installment Schedule")
    payment_reminder_days = fields.Integer(
        string="Reminder Days",
        default=5,
        help="Number of days before due date when the accountant should be notified.",
    )

    signatory_page2_name = fields.Char(string="Page 2 Signatory Name")
    signatory_page2_title = fields.Char(string="Page 2 Signatory Title")
    signatory_final_name = fields.Char(string="Final Page Signatory Name")
    signatory_final_title = fields.Char(string="Final Page Signatory Title")

    article_ids = fields.One2many("qlk.engagement.article.line", "engagement_id", string="Articles")

    # Retainer tracking fields
    retainer_corporate_monthly_hour_cap = fields.Float(string="Corporate Monthly Hour Cap")
    retainer_corporate_yearly_hour_cap = fields.Float(
        string="Corporate Yearly Hour Cap",
        compute="_compute_corporate_yearly_cap",
        store=True,
    )
    corporate_usage_ids = fields.One2many("qlk.engagement.corporate.log", "engagement_id", string="Corporate Usage Logs")
    corporate_alert_ids = fields.One2many("qlk.engagement.corporate.alert", "engagement_id", string="Corporate Alerts")
    corporate_hours_month_to_date = fields.Float(
        string="Hours (Current Month)",
        compute="_compute_corporate_usage",
        help="Hours consumed during the month of the engagement letter date.",
    )
    corporate_hours_year_to_date = fields.Float(
        string="Hours (Year To Date)",
        compute="_compute_corporate_usage",
    )
    corporate_hours_remaining = fields.Float(
        string="Remaining Monthly Hours",
        compute="_compute_corporate_usage",
    )
    # Financial estimates derived from proposals

    @api.depends("estimated_hours", "hourly_rate", "additional_cost")
    def _compute_estimated_total(self):
        for record in self:
            hours_total = (record.estimated_hours or 0.0) * (record.hourly_rate or 0.0)
            record.estimated_total = hours_total + (record.additional_cost or 0.0)

    @api.depends("cost_calculation_id.total", "cost_additional_amount")
    def _compute_cost_amounts(self):
        for record in self:
            base = record.cost_calculation_id.total if record.cost_calculation_id else 0.0
            additional = record.cost_additional_amount or 0.0
            record.cost_base_amount = base
            record.cost_total_amount = base + additional

    @api.model
    def _get_cost_calculation_for_employee_id(self, employee_id):
        if not employee_id:
            return self.env["cost.calculation"]
        return self.env["cost.calculation"].search(
            [("employee_id", "=", employee_id)],
            limit=1,
        )

    def _apply_cost_calculation(self):
        for record in self:
            desired = self._get_cost_calculation_for_employee_id(record.employee_id.id if record.employee_id else False)
            desired_id = desired.id if desired else False
            if record.cost_calculation_id.id != desired_id:
                record.with_context(skip_cost_sync=True).write({"cost_calculation_id": desired_id})

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        cost_calc = self._get_cost_calculation_for_employee_id(self.employee_id.id if self.employee_id else False)
        self.cost_calculation_id = cost_calc

    monthly_hours = fields.Float(
        string="Monthly Hours",
        related="retainer_corporate_monthly_hour_cap",
        store=True,
        readonly=False,
    )
    yearly_hours = fields.Float(
        string="Yearly Hours",
        related="retainer_corporate_yearly_hour_cap",
        store=True,
        readonly=True,
    )
    retainer_litigation_case_limit = fields.Integer(string="Litigation Case Limit")
    litigation_case_ids = fields.One2many(
        "qlk.engagement.litigation.case",
        "engagement_id",
        string="Litigation Cases",
    )
    litigation_limit_reached = fields.Boolean(string="Litigation Limit Reached", default=False, readonly=True)
    litigation_case_count = fields.Integer(
        string="Litigation Case Count",
        compute="_compute_litigation_case_count",
        store=False,
    )
    max_cases = fields.Integer(
        string="Maximum Cases",
        related="retainer_litigation_case_limit",
        store=True,
        readonly=False,
    )
    total_cases = fields.Integer(
        string="Total Cases",
        compute="_compute_litigation_case_count",
        store=False,
    )

    _sql_constraints = [
        ("reference_unique", "unique(reference)", "The engagement letter reference must be unique."),
    ]

    @api.depends("approval_state")
    def _compute_can_print(self):
        for record in self:
            record.can_print = record.approval_state == "approved"

    @api.depends("date")
    def _compute_year(self):
        today = fields.Date.context_today(self)
        for record in self:
            reference_date = record.date or today
            if isinstance(reference_date, str):
                reference_date = fields.Date.from_string(reference_date)
            record.year = reference_date.year

    @api.depends("retainer_corporate_monthly_hour_cap")
    def _compute_corporate_yearly_cap(self):
        for record in self:
            record.retainer_corporate_yearly_hour_cap = record.retainer_corporate_monthly_hour_cap * 12.0

    @api.depends(
        "corporate_usage_ids.hours",
        "corporate_usage_ids.date",
        "retainer_corporate_monthly_hour_cap",
    )
    def _compute_corporate_usage(self):
        today = fields.Date.context_today(self)
        for record in self:
            monthly_total = 0.0
            yearly_total = 0.0
            for usage in record.corporate_usage_ids:
                if not usage.date:
                    continue
                if usage.date.year == today.year:
                    yearly_total += usage.hours
                if usage.date.year == today.year and usage.date.month == today.month:
                    monthly_total += usage.hours
            record.corporate_hours_month_to_date = monthly_total
            record.corporate_hours_year_to_date = yearly_total
            record.corporate_hours_remaining = max(
                record.retainer_corporate_monthly_hour_cap - monthly_total, 0.0
            )

    @api.depends("litigation_case_ids")
    def _compute_litigation_case_count(self):
        for record in self:
            record.litigation_case_count = len(record.litigation_case_ids)
            record.total_cases = record.litigation_case_count

    @api.onchange("contract_type")
    def _onchange_contract_type(self):
        if self.contract_type == "retainer":
            self.state = "active"
        if self.contract_type != "retainer":
            self.retainer_scope = False

    @api.onchange("retainer_scope")
    def _onchange_retainer_scope(self):
        if self.contract_type != "retainer":
            return
        scope_to_department = {
            "corporate": "C",
            "litigation": "L",
            "both": "CL",
        }
        if self.retainer_scope:
            self.department_type = scope_to_department.get(self.retainer_scope, "C")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if not self.partner_id:
            return
        self.client_type = "company" if self.partner_id.is_company else "individual"
        if self.client_type == "individual":
            self.individual_full_name = self.partner_id.name
            self.individual_email = self.partner_id.email
            self.individual_phone = self.partner_id.phone or self.partner_id.mobile
        else:
            self.company_name = self.partner_id.name
            self.company_email = self.partner_id.email
            self.company_phone = self.partner_id.phone or self.partner_id.mobile
            self.company_location = ", ".join(filter(None, [self.partner_id.city, self.partner_id.country_id.name]))
        self.client_unique_code = self.partner_id.engagement_client_code

    @api.constrains("contract_type", "retainer_scope", "department_type")
    def _check_contract_configuration(self):
        for record in self:
            if record.contract_type == "retainer" and not record.retainer_scope:
                raise ValidationError(_("Please select the retainer coverage scope."))
            if record.contract_type == "retainer":
                scope_to_department = {
                    "corporate": "C",
                    "litigation": "L",
                    "both": "CL",
                }
                expected_department = scope_to_department.get(record.retainer_scope)
                if expected_department and record.department_type != expected_department:
                    raise ValidationError(_("Department type must align with the retainer scope."))
            if record.department_type == "CL" and not (
                record.contract_type == "retainer" and record.retainer_scope == "both"
            ):
                raise ValidationError(
                    _(
                        "A combined (CL) engagement must be configured as a retainer covering both corporate and litigation services."
                    )
                )

    @api.constrains("individual_qid", "individual_passport", "client_type")
    def _check_identification(self):
        for record in self:
            if record.client_type != "individual":
                continue
            if not record.individual_qid and not record.individual_passport:
                raise ValidationError(_("Provide either the Qatar ID or Passport number for the individual client."))
            if record.individual_qid and record.individual_passport:
                raise ValidationError(_("Provide only one identifier: Qatar ID or Passport number."))

    @api.constrains("retainer_corporate_monthly_hour_cap", "retainer_litigation_case_limit", "contract_type", "retainer_scope")
    def _check_retainer_limits(self):
        for record in self:
            if record.contract_type != "retainer":
                continue
            if record.retainer_scope in ("corporate", "both") and record.retainer_corporate_monthly_hour_cap <= 0:
                raise ValidationError(_("Set a positive monthly hour cap for the corporate retainer."))
            if record.retainer_scope in ("litigation", "both") and record.retainer_litigation_case_limit <= 0:
                raise ValidationError(_("Specify the maximum number of litigation cases covered by the retainer."))

    @api.model
    def _get_sequence_code_for_department(self, department_type):
        return f"qlk.engagement.letter.{department_type}"

    def _get_reference_sequence_date(self, vals):
        letter_date = vals.get("date")
        if not letter_date and "date" not in vals:
            return fields.Date.context_today(self)
        if isinstance(letter_date, str):
            return fields.Date.from_string(letter_date)
        return letter_date

    @api.model_create_multi
    def create(self, vals_list):
        sequence_model = self.env["qlk.engagement.sequence"]
        templates = self.env["qlk.engagement.article.template"]
        for vals in vals_list:
            vals.setdefault("state", "draft")
            vals.setdefault("approval_state", "draft")
            vals.setdefault("requester_id", self.env.user.id)
            vals.setdefault("company_id", self.env.company.id)
            contract_type = vals.get("contract_type", "retainer")
            if contract_type != "retainer":
                vals["retainer_scope"] = False
            scope = vals.get("retainer_scope")
            if contract_type == "retainer" and scope:
                vals["department_type"] = self.SCOPE_TO_DEPARTMENT.get(scope, vals.get("department_type"))
            department_type = vals.get("department_type") or "C"
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            reference, serial, _seq_year = sequence_model._next_reference(department_type, company)
            vals["reference"] = reference
            vals["name"] = reference
            vals.setdefault("serial_number", serial)
            if not vals.get("article_ids"):
                vals["article_ids"] = [
                    Command.create(
                        {
                            "template_id": template.id,
                            "name": template.name,
                            "content": template.content,
                            "is_editable": template.is_editable,
                        }
                    )
                    for template in templates.search([("active", "=", True)], order="sequence asc, id asc")
                ]
            employee_id = vals.get("employee_id")
            if employee_id and not vals.get("cost_calculation_id"):
                cost_calc = self._get_cost_calculation_for_employee_id(employee_id)
                vals["cost_calculation_id"] = cost_calc.id if cost_calc else False
        letters = super().create(vals_list)
        letters._apply_cost_calculation()
        for letter in letters:
            if letter.contract_type == "retainer" and letter.retainer_scope in ("corporate", "both"):
                letter.state = "active"
            if letter.partner_id and letter.partner_id.engagement_client_code:
                letter.client_unique_code = letter.partner_id.engagement_client_code
            if letter.payment_type == "paid" and not letter.total_fees:
                letter.total_fees = letter.estimated_total
            elif letter.payment_type == "pro_bono":
                letter.total_fees = 0.0
        return letters

    def write(self, vals):
        if self.env.context.get("skip_cost_sync"):
            return super().write(vals)
        vals = dict(vals)
        previous_states = {record.id: record.approval_state for record in self}
        signed_document_in_vals = "signed_document" in vals
        if "contract_type" in vals and vals["contract_type"] != "retainer":
            vals["retainer_scope"] = False
        if "retainer_scope" in vals:
            scope = vals.get("retainer_scope")
            if scope and (
                (vals.get("contract_type") == "retainer")
                or ("contract_type" not in vals and all(record.contract_type == "retainer" for record in self))
            ):
                vals["department_type"] = self.SCOPE_TO_DEPARTMENT.get(scope, vals.get("department_type"))
        result = super().write(vals)
        if "employee_id" in vals:
            self._apply_cost_calculation()
        if signed_document_in_vals:
            for record in self:
                if record.signed_document:
                    record.signed_document_uploaded_on = fields.Datetime.now()
                    record.signed_document_uploaded_by = self.env.user
                else:
                    record.signed_document_uploaded_on = False
                    record.signed_document_uploaded_by = False
        if "approval_state" in vals:
            for record in self:
                previous_state = previous_states.get(record.id)
                if previous_state != record.approval_state:
                    record._post_approval_state_change(previous_state)
        if any(field in vals for field in ["retainer_corporate_monthly_hour_cap", "retainer_scope", "contract_type"]):
            for letter in self:
                letter._recalculate_corporate_alerts()
        if any(field in vals for field in ["retainer_litigation_case_limit", "retainer_scope", "contract_type"]):
            for letter in self:
                letter._evaluate_litigation_limits()
        if any(field in vals for field in ["estimated_hours", "hourly_rate", "additional_cost", "payment_type"]):
            for letter in self:
                if letter.payment_type == "paid" and ("total_fees" not in vals or vals.get("total_fees") is None):
                    letter.total_fees = letter.estimated_total
                elif letter.payment_type == "pro_bono" and "total_fees" not in vals:
                    letter.total_fees = 0.0
        return result

    def _post_approval_state_change(self, previous_state):
        self.ensure_one()
        if self.approval_state == "waiting":
            self.approval_requested_on = fields.Datetime.now()
            self.approval_decision_on = False
            self.approval_comment = False
            self.rejection_reason = False
            self._notify_approver_submission()
        elif self.approval_state == "approved":
            self.approval_decision_on = fields.Datetime.now()
            self.rejection_reason = False
            self._assign_client_unique_code()
            self._notify_requester_approval()
        elif self.approval_state == "rejected":
            self.approval_decision_on = fields.Datetime.now()
            self._notify_requester_rejection()

    def _ensure_can_approve(self):
        if not self.env.user.has_group("qlk_proposals_engagement_letter.group_engagement_manager"):
            raise ValidationError(_("Only engagement managers can approve or reject engagement letters."))

    def action_submit_for_approval(self):
        for record in self:
            if record.approval_state not in ("draft", "rejected"):
                raise ValidationError(_("Only draft or returned engagement letters can be submitted for approval."))
            if not record.approver_id:
                record.approver_id = record._default_approver()
            record.approval_state = "waiting"
        return True

    def action_approve(self):
        self._ensure_can_approve()
        for record in self:
            if record.approval_state != "waiting":
                raise ValidationError(_("Only engagement letters waiting for approval can be approved."))
            record.approval_state = "approved"
            record.action_mark_project_approved()
        return True

    def action_reject(self):
        self._ensure_can_approve()
        for record in self:
            if record.approval_state != "waiting":
                raise ValidationError(_("Only engagement letters waiting for approval can be rejected."))
            if not record.rejection_reason:
                raise ValidationError(_("Please provide a rejection reason before rejecting the engagement letter."))
            record.approval_state = "rejected"
        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.approval_state != "rejected":
                raise ValidationError(_("Only returned engagement letters can be sent back to preparation."))
            record.approval_state = "draft"
        return True

    def action_mark_project_approved(self):
        self._ensure_can_approve()
        for record in self:
            if record.is_approved:
                continue
            values = {
                'is_approved': True,
                'approval_user_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            }
            if record.state == 'draft':
                values['state'] = 'approved'
            if record.approval_state != "approved":
                values["approval_state"] = "approved"
            record.write(values)
            record.message_post(
                body=_("The engagement letter has been approved for project creation."),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _map_department_to_project(self):
        mapping = {
            "C": "corporate",
            "L": "litigation",
            "A": "arbitration",
            "CL": "corporate",
        }
        return mapping.get(self.department_type, "litigation")

    def action_create_project(self):
        self.ensure_one()
        if "qlk.project" not in self.env:
            raise ValidationError(_("The project management module must be installed to create a project."))
        if not self.is_approved:
            raise ValidationError(_("The engagement letter must be approved before creating a project."))
        if not self.partner_id:
            raise ValidationError(_("Please set a client on the engagement letter before creating a project."))
        Project = self.env["qlk.project"]
        if self.project_id:
            return self.action_open_project()
        project_vals = {
            "name": self.reference or self.name or _("New Project"),
            "client_id": self.partner_id.id,
            "department": self._map_department_to_project(),
            "engagement_id": self.id,
            "description": self.scope_of_work,
        }
        project = Project.create(project_vals)
        self.write(
            {
                "project_id": project.id,
                "state": "active",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "qlk.project",
            "res_id": project.id,
            "view_mode": "form",
        }

    def action_open_project(self):
        self.ensure_one()
        if not self.project_id:
            raise ValidationError(_("No project has been created from this engagement letter yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "qlk.project",
            "res_id": self.project_id.id,
            "view_mode": "form",
        }

    def action_print_letter(self):
        self.ensure_one()
        if not self.can_print:
            raise ValidationError(_("The engagement letter must be approved before it can be printed."))
        return self.env.ref("qlk_proposals_engagement_letter.action_report_engagement_letter").report_action(self)

    def _default_approver(self):
        manager_group = self.env.ref("qlk_proposals_engagement_letter.group_engagement_manager", raise_if_not_found=False)
        if manager_group and manager_group.users:
            return manager_group.users[0]
        return self.env.user

    def _assign_client_unique_code(self):
        if not self.partner_id:
            return
        if self.partner_id.engagement_client_code:
            self.client_unique_code = self.partner_id.engagement_client_code
            return
        sequence_code = "qlk.engagement.client.code"
        next_code = self.env["ir.sequence"].next_by_code(sequence_code)
        if not next_code:
            raise ValidationError(_("Please configure the engagement client code sequence."))
        self.partner_id.engagement_client_code = next_code
        self.client_unique_code = next_code

    def action_open_corporate_usage(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Corporate Usage"),
            "res_model": "qlk.engagement.corporate.log",
            "view_mode": "list,form",
            "domain": [("engagement_id", "=", self.id)],
            "context": {"default_engagement_id": self.id},
        }

    def action_open_litigation_cases(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Litigation Cases"),
            "res_model": "qlk.engagement.litigation.case",
            "view_mode": "list,form",
            "domain": [("engagement_id", "=", self.id)],
            "context": {"default_engagement_id": self.id},
        }

    def action_set_active(self):
        for record in self:
            if record.approval_state != "approved":
                raise ValidationError(_("The engagement letter must be approved before it can be activated."))
            record.state = "active"
        return True

    def action_set_closed(self):
        for record in self:
            record.state = "closed"
        return True

    def action_set_cancelled(self):
        for record in self:
            record.state = "cancelled"
        return True

    def _notification_partners(self):
        partners = self.env["res.partner"]
        try:
            partners |= self.env.ref("qlk_law.group_qlk_law_manager").users.mapped("partner_id")
        except ValueError:
            partners |= self.env.user.partner_id
        try:
            partners |= self.env.ref("qlk_law.group_qlk_law_manager").users.mapped("partner_id")
        except ValueError:
            partners |= self.env.user.partner_id
        return partners

    def _notify_approver_submission(self):
        partners = self.approver_id.partner_id
        if not partners:
            partners = self._notification_partners()
        body = _(
            "The engagement letter %(reference)s has been submitted for approval by %(requester)s.",
            reference=self.reference,
            requester=self.requester_id.name if self.requester_id else self.env.user.name,
        )
        self.message_post(body=body, partner_ids=partners.ids, subtype_xmlid="mail.mt_comment")

    def _notify_requester_approval(self):
        if not self.requester_id:
            return
        body = _(
            "The engagement letter %(reference)s has been approved.",
            reference=self.reference,
        )
        self.message_post(body=body, partner_ids=[self.requester_id.partner_id.id], subtype_xmlid="mail.mt_comment")

    def _notify_requester_rejection(self):
        if not self.requester_id:
            return
        body = _(
            "The engagement letter %(reference)s has been returned with the following reason: %(reason)s",
            reference=self.reference,
            reason=self.rejection_reason or _("No reason provided."),
        )
        self.message_post(body=body, partner_ids=[self.requester_id.partner_id.id], subtype_xmlid="mail.mt_comment")

    def _notify_corporate_overage(self, month, year, hours_over):
        partners = self._notification_partners()
        template = self.env.ref("qlk_proposals_engagement_letter.mail_template_engagement_corporate_overage", raise_if_not_found=False)
        if template:
            month_name = date(year, month, 1).strftime("%B")
            ctx = {
                "notification_month": month,
                "notification_month_name": month_name,
                "notification_year": year,
                "hours_over": hours_over,
                "hour_cap": self.retainer_corporate_monthly_hour_cap,
            }
            template = template.with_context(**ctx)
            template.send_mail(self.id, force_send=True, email_values={"recipient_ids": [Command.set(partners.ids)]})
        message_body = _(
            "Corporate retainer usage for %(month)s %(year)s reached %(hours)s hours which exceeds "
            "the monthly cap of %(cap)s hours.",
            month=date(year, month, 1).strftime("%B"),
            year=year,
            hours=hours_over,
            cap=self.retainer_corporate_monthly_hour_cap,
        )
        self.message_post(body=message_body, partner_ids=partners.ids, subtype_xmlid="mail.mt_note")

    def _notify_litigation_overage(self):
        partners = self._notification_partners()
        template = self.env.ref("qlk_proposals_engagement_letter.mail_template_engagement_litigation_overage", raise_if_not_found=False)
        if template:
            ctx = {
                "litigation_limit": self.retainer_litigation_case_limit,
                "litigation_total": len(self.litigation_case_ids),
            }
            template = template.with_context(**ctx)
            template.send_mail(self.id, force_send=True, email_values={"recipient_ids": [Command.set(partners.ids)]})
        message_body = _(
            "The litigation retainer limit of %(limit)s cases has been exceeded. Total tracked cases: %(total)s.",
            limit=self.retainer_litigation_case_limit,
            total=len(self.litigation_case_ids),
        )
        self.message_post(body=message_body, partner_ids=partners.ids, subtype_xmlid="mail.mt_note")

    def _recalculate_corporate_alerts(self):
        for record in self:
            record.corporate_alert_ids.sudo().unlink()
            if record.contract_type != "retainer" or record.retainer_scope not in ("corporate", "both"):
                continue
            record._evaluate_corporate_usage_alerts()

    def _evaluate_corporate_usage_alerts(self, reference_date=None):
        self.ensure_one()
        if self.retainer_corporate_monthly_hour_cap <= 0:
            return
        logs = self.corporate_usage_ids
        months_to_check = set()
        if reference_date:
            months_to_check.add((reference_date.year, reference_date.month))
        else:
            months_to_check = {(log.date.year, log.date.month) for log in logs if log.date}
        for year, month in months_to_check:
            monthly_total = sum(
                log.hours for log in logs if log.date and log.date.year == year and log.date.month == month
            )
            if monthly_total > self.retainer_corporate_monthly_hour_cap:
                existing_alert = self.corporate_alert_ids.filtered(lambda a: a.year == year and a.month == month)
                alert = existing_alert[:1]
                if not alert:
                    alert = self.env["qlk.engagement.corporate.alert"].create(
                        {
                            "engagement_id": self.id,
                            "year": year,
                            "month": month,
                            "hours": monthly_total,
                            "notified_on": fields.Date.context_today(self),
                        }
                    )
                else:
                    alert.write({"hours": monthly_total})
                if not alert.notified:
                    alert.write(
                        {
                            "notified": True,
                            "notified_on": fields.Date.context_today(self),
                        }
                    )
                    self._notify_corporate_overage(month, year, monthly_total)
            else:
                alert = self.corporate_alert_ids.filtered(lambda a: a.year == year and a.month == month)
                if alert:
                    alert.write({"hours": monthly_total, "notified": False, "notified_on": False})

    def _after_corporate_usage_change(self, reference_date=None):
        self._evaluate_corporate_usage_alerts(reference_date=reference_date)
        self._compute_corporate_usage()

    def _evaluate_litigation_limits(self):
        self.ensure_one()
        if self.contract_type != "retainer" or self.retainer_scope not in ("litigation", "both"):
            self.litigation_limit_reached = False
            return
        case_count = len(self.litigation_case_ids)
        if self.retainer_litigation_case_limit and case_count > self.retainer_litigation_case_limit:
            if not self.litigation_limit_reached:
                self._notify_litigation_overage()
            self.litigation_limit_reached = True
        else:
            self.litigation_limit_reached = False


class EngagementInstallment(models.Model):
    _name = "qlk.engagement.installment"
    _description = "Engagement Letter Installment"
    _order = "due_date asc, sequence asc, id asc"

    engagement_id = fields.Many2one("qlk.engagement.letter", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    description = fields.Char(string="Installment Description")
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(
        "res.currency",
        related="engagement_id.currency_id",
        readonly=True,
        store=True,
    )
    due_date = fields.Date(required=True)
    state = fields.Selection(
        selection=[("pending", "Pending"), ("invoiced", "Invoiced"), ("paid", "Paid"), ("cancelled", "Cancelled")],
        default="pending",
        required=True,
    )
    reminder_sent = fields.Boolean(default=False)

    def action_mark_invoiced(self):
        for record in self:
            record.state = "invoiced"
        return True

    def action_mark_paid(self):
        for record in self:
            record.state = "paid"
        return True

    def action_reset_reminder(self):
        for record in self:
            record.reminder_sent = False
        return True

    def write(self, vals):
        need_reset = any(key in vals for key in ["due_date", "amount", "state"])
        result = super().write(vals)
        if need_reset:
            for record in self.filtered(lambda inst: inst.state == "pending" and inst.reminder_sent):
                super(EngagementInstallment, record).write({"reminder_sent": False})
        return result

    def _notify_upcoming_payment(self):
        self.ensure_one()
        partners = self.engagement_id._notification_partners()
        template = self.env.ref("qlk_proposals_engagement_letter.mail_template_engagement_installment_due", raise_if_not_found=False)
        if template:
            ctx = {
                "installment_amount": self.amount,
                "installment_due_date": self.due_date,
                "installment_description": self.description,
            }
            template = template.with_context(**ctx)
            template.send_mail(self.engagement_id.id, force_send=True, email_values={"recipient_ids": [Command.set(partners.ids)]})
        message_body = _(
            "Installment '%(description)s' for %(amount).2f %(currency)s is due on %(due)s.",
            description=self.description or _("Installment"),
            amount=self.amount,
            currency=self.currency_id.symbol,
            due=self.due_date,
        )
        self.engagement_id.message_post(body=message_body, partner_ids=partners.ids, subtype_xmlid="mail.mt_note")
        self.reminder_sent = True

    @api.model
    def cron_notify_upcoming_installments(self):
        today = fields.Date.context_today(self)
        installments = self.search(
            [
                ("state", "=", "pending"),
                ("reminder_sent", "=", False),
                ("due_date", "!=", False),
            ]
        )
        for installment in installments:
            if installment.engagement_id.payment_reminder_days < 0 or not installment.due_date:
                continue
            reminder_date = installment.due_date - timedelta(days=installment.engagement_id.payment_reminder_days)
            if reminder_date <= today <= installment.due_date:
                installment._notify_upcoming_payment()


class EngagementCorporateUsage(models.Model):
    _name = "qlk.engagement.corporate.log"
    _description = "Corporate Retainer Usage Log"
    _order = "date desc, id desc"

    engagement_id = fields.Many2one("qlk.engagement.letter", required=True, ondelete="cascade")
    date = fields.Date(default=lambda self: fields.Date.context_today(self), required=True)
    hours = fields.Float(required=True)
    description = fields.Char()
    work_id = fields.Many2one("qlk.work", string="Related Work Item")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.engagement_id._after_corporate_usage_change(reference_date=record.date)
        return records

    def write(self, vals):
        result = super().write(vals)
        for record in self:
            reference_date = vals.get("date") or record.date
            record.engagement_id._after_corporate_usage_change(reference_date=reference_date)
        return result

    def unlink(self):
        engagement_mapping = {}
        for record in self:
            engagement_mapping.setdefault(record.engagement_id, set()).add(record.date)
        result = super().unlink()
        for engagement, dates in engagement_mapping.items():
            for reference_date in dates:
                engagement._after_corporate_usage_change(reference_date=reference_date)
        return result


class EngagementCorporateAlert(models.Model):
    _name = "qlk.engagement.corporate.alert"
    _description = "Corporate Retainer Alert"
    _order = "year desc, month desc, id desc"

    engagement_id = fields.Many2one("qlk.engagement.letter", required=True, ondelete="cascade")
    year = fields.Integer(required=True)
    month = fields.Integer(required=True)
    hours = fields.Float(required=True)
    notified_on = fields.Date()
    notified = fields.Boolean(default=False)


class EngagementLitigationCase(models.Model):
    _name = "qlk.engagement.litigation.case"
    _description = "Litigation Cases Under Retainer"
    _order = "open_date desc, id desc"

    engagement_id = fields.Many2one("qlk.engagement.letter", required=True, ondelete="cascade")
    case_id = fields.Many2one("qlk.case", string="Case", ondelete="set null")
    name = fields.Char(string="Case Reference")
    open_date = fields.Date(default=lambda self: fields.Date.context_today(self))
    notes = fields.Text(string="Notes")

    @api.onchange("case_id")
    def _onchange_case_id(self):
        if self.case_id:
            self.name = self.case_id.name
            self.open_date = self.case_id.start_date or fields.Date.context_today(self)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.engagement_id._evaluate_litigation_limits()
        return records

    def unlink(self):
        engagements = self.mapped("engagement_id")
        result = super().unlink()
        for engagement in engagements:
            engagement._evaluate_litigation_limits()
        return result


class EngagementArticleTemplate(models.Model):
    _name = "qlk.engagement.article.template"
    _description = "Default Engagement Letter Article"

    name = fields.Char(required=True)
    content = fields.Html(required=True, sanitize=False)
    is_editable = fields.Boolean(default=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class EngagementArticleLine(models.Model):
    _name = "qlk.engagement.article.line"
    _description = "Engagement Letter Article Line"
    _order = "sequence asc, id asc"

    engagement_id = fields.Many2one("qlk.engagement.letter", required=True, ondelete="cascade")
    template_id = fields.Many2one("qlk.engagement.article.template", ondelete="set null")
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    content = fields.Html(sanitize=False)
    is_editable = fields.Boolean(default=False)
    SCOPE_TO_DEPARTMENT = {
        "corporate": "C",
        "litigation": "L",
        "both": "CL",
    }
