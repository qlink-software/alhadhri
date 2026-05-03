# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# Engagement Letter (EL)
# هذا الموديل يمثل العقد الرسمي مع العميل ويتضمن منطق التسعير والساعات
# ونظام الموافقة والترقيم التلقائي مرهون بنوع العقد والسنة المالية.
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PROJECT_TYPE_SELECTION = [
    ("cm", "CM"),
    ("lm", "LM"),
    ("lc", "LC"),
    ("corporate", "Corporate"),
    ("litigation", "Litigation"),
    ("arbitration", "Arbitration"),
]

DOCUMENT_TYPE_SELECTION = [
    ("proposal", "Proposal"),
    ("engagement_letter", "Engagement Letter"),
]

PAYMENT_STATUS_SELECTION = [
    ("unpaid", "Unpaid"),
    ("partial", "Partially Paid"),
    ("paid", "Paid"),
]

TRANSLATION_STATUS_SELECTION = [
    ("draft", "Draft"),
    ("sent", "Sent to Translation"),
    ("done", "Translated"),
]


class BDEngagementLetter(models.Model):
    _name = "bd.engagement.letter"
    _description = "Engagement Letter"
    _inherit = ["mail.thread", "mail.activity.mixin", "qlk.notification.mixin", "bd.retainer.mixin"]
    _order = "create_date desc"
    _rec_name = "code"

    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    reference = fields.Char(string="Reference", tracking=True)
    code = fields.Char(string="Engagement Letter Code", default="/", copy=False, readonly=True)
    contract_type = fields.Selection(
        [
            ("hours", "Hours Based"),
            ("cases", "Case Based"),
            ("retainer", "Retainer (Legacy)"),
            ("lump_sum", "Lump Sum (Legacy)"),
        ],
        string="Contract Type",
        required=True,
        default="hours",
        tracking=True,
    )
    service_type = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("pre_litigation", "Pre-Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("mixed", "Mixed"),
        ],
        string="Service Type",
        default="corporate",
        tracking=True,
    )
    litigation_degree_ids = fields.Many2many(
        "qlk.litigation.degree",
        "bd_engagement_litigation_degree_rel",
        "engagement_id",
        "degree_id",
        string="Allowed Litigation Degrees",
        tracking=True,
    )
    retainer_type = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("litigation_corporate", "Litigation + Corporate"),
            ("management_corporate", "Management Corporate"),
            ("management_litigation", "Management Litigation"),
        ],
        string="Services Type",
        default="corporate",
        tracking=True,
    )
    monthly_corporate_hours = fields.Float(string="Monthly Corporate Hours")
    yearly_hours = fields.Float(
        string="Yearly Hours", compute="_compute_yearly_hours", store=True
    )
    litigation_cases_limit = fields.Integer(string="Litigation Cases Limit")
    agreed_hours = fields.Float(string="Agreed Hours", tracking=True)
    agreed_case_count = fields.Integer(string="Agreed Case Count", tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True, tracking=True
    )
    client_document_ids = fields.One2many(
        related="partner_id.client_document_ids",
        string="Client Documents",
    )
    client_attachment_ids = fields.Many2many(
        related="partner_id.client_attachment_ids",
        string="Client Attachments",
        readonly=False,
    )
    translation_attachment_ids = fields.Many2many(
        "ir.attachment",
        "bd_engagement_translation_attachment_rel",
        "letter_id",
        "attachment_id",
        string="Attachments Needing Translation",
        tracking=True,
    )
    translation_status = fields.Selection(
        TRANSLATION_STATUS_SELECTION,
        string="Translation Status",
        default="draft",
        tracking=True,
    )
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        compute="_compute_client_id",
        inverse="_inverse_client_id",
        store=True,
        index=True,
    )
    engagement_type = fields.Selection(
        selection=PROJECT_TYPE_SELECTION,
        string="Engagement Type",
        tracking=True,
    )
    contact_details = fields.Text(string="Contact Details")
    fee_total = fields.Monetary(
        string="Fee Total",
        currency_field="currency_id",
        compute="_compute_fee_total",
        store=True,
    )
    fee_line_ids = fields.One2many(
        "bd.engagement.letter.fee", "letter_id", string="Fee Breakdown"
    )
    legal_fees_lines = fields.One2many(
        "bd.engagement.letter.fee",
        "letter_id",
        string="Legal Fees Lines",
    )
    total_legal_fees = fields.Monetary(
        string="Total Legal Fees",
        currency_field="currency_id",
        compute="_compute_total_fees",
        store=True,
    )
    scope_of_work = fields.Text(string="Scope of Work")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    reviewer_id = fields.Many2one(
        "res.users", string="Reviewer", default=lambda self: self.env.user, index=True
    )
    client_code = fields.Char(string="Client Code", readonly=True, copy=False)
    project_type = fields.Selection(
        selection=PROJECT_TYPE_SELECTION,
        string="Project Type",
        default="corporate",
        tracking=True,
    )
    billing_type = fields.Selection(
        [
            ("free", "Pro bono"),
            ("paid", "Paid"),
        ],
        string="Billing Type",
        default="paid",
        tracking=True,
    )
    retainer_period = fields.Selection(
        [("annual", "Annual"), ("monthly", "Monthly")],
        string="Retainer Type",
        tracking=True,
    )
    allocated_hours = fields.Float(string="Allocated Hours", tracking=True)
    used_hours = fields.Float(
        string="Used Hours",
        compute="_compute_used_hours",
        store=True,
        readonly=True,
    )
    remaining_hours = fields.Float(
        string="Remaining Hours",
        compute="_compute_remaining_hours",
        store=True,
        readonly=True,
    )
    total_hours_used = fields.Float(
        string="Total Hours Used",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    over_consumed = fields.Boolean(
        string="Over Consumed",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    consumption_label = fields.Char(
        string="Consumption Status",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    total_cases = fields.Integer(
        string="Total Cases",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    remaining_cases = fields.Integer(
        string="Remaining Cases",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    case_count = fields.Integer(
        string="Cases",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    pre_litigation_count = fields.Integer(
        string="Pre-Litigation",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    corporate_count = fields.Integer(
        string="Corporate",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    arbitration_count = fields.Integer(
        string="Arbitration",
        compute="_compute_engagement_consumption",
        store=True,
        readonly=True,
    )
    monthly_hours_limit = fields.Float(string="Monthly Hours Limit", tracking=True)
    monthly_used_hours = fields.Float(
        string="Monthly Used Hours",
        compute="_compute_monthly_used_hours",
        readonly=True,
    )
    year_start_date = fields.Date(string="Year Start Date", tracking=True)
    year_end_date = fields.Date(string="Year End Date", tracking=True)
    exception_approved = fields.Boolean(string="Exception Approved", tracking=True)
    retainer_usage_percent = fields.Float(
        string="Retainer Usage %",
        compute="_compute_retainer_usage_percent",
        readonly=True,
    )
    retainer_usage_state = fields.Selection(
        [
            ("normal", "Normal"),
            ("success", "Healthy"),
            ("warning", "Warning"),
            ("danger", "Critical"),
        ],
        string="Retainer Usage State",
        compute="_compute_retainer_usage_percent",
        readonly=True,
    )
    last_retainer_alert_key = fields.Char(
        string="Last Retainer Alert Period",
        copy=False,
        readonly=True,
    )
    estimated_hours = fields.Float(string="Estimated Hours")
    fee_structure = fields.Char(string="Fee Structure")
    payment_terms = fields.Char(string="Payment Terms")
    legal_note = fields.Text(string="Legal Notes")
    legal_fee_amount = fields.Monetary(
        string="Legal Fees",
        currency_field="currency_id",
    )
    proposal_legal_fee = fields.Monetary(
        string="Proposal Legal Fees",
        currency_field="currency_id",
        compute="_compute_proposal_legal_fee",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_manager_approval", "Waiting Manager Approval"),
            ("approved_manager", "Approved by Manager"),
            ("waiting_client_approval", "Waiting Client Approval"),
            ("approved_client", "Approved by Client"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        group_expand="_group_expand_states",
    )

    @api.model
    def _group_expand_states(self, states, domain, order=None):
        return [
            "draft",
            "waiting_manager_approval",
            "approved_manager",
            "waiting_client_approval",
            "approved_client",
            "rejected",
            "cancelled",
        ]

    def init(self):
        # Normalize legacy billing values introduced during previous customizations.
        self._cr.execute(
            """
            UPDATE bd_engagement_letter
               SET billing_type = 'paid'
             WHERE billing_type IN ('billable', 'fixed', 'retainer')
            """
        )
    rejection_reason = fields.Text(string="Rejection Reason")
    comments = fields.Text(string="Reason")
    # ------------------------------------------------------------------------------
    # يحتفظ بمرجع العرض الذي أنشأ هذه الاتفاقية لتسهيل التتبع وإعادة الفتح.
    # ------------------------------------------------------------------------------
    proposal_id = fields.Many2one("bd.proposal", string="Source Proposal", copy=False)
    signed_document_id = fields.Many2one(
        "ir.attachment",
        string="Signed Copy",
        help="Upload the signed Engagement Letter after approval.",
        index=True,
    )
    signed_document_ids = fields.Many2many(
        "ir.attachment",
        "bd_engagement_letter_signed_document_rel",
        "letter_id",
        "attachment_id",
        string="Signed Copy",
        help="Upload the signed Engagement Letter after approval.",
    )
    signed_on = fields.Datetime(string="Signed On", readonly=True)
    client_code_generated = fields.Boolean(string="Client Code Generated", readonly=True, copy=False)
    lawyer_id = fields.Many2one(
        "res.partner",
        string="Assigned Lawyer",
        domain=[("is_lawyer", "=", True)],
    )
    lawyer_ids = fields.Many2many(
        "hr.employee",
        "bd_engagement_letter_lawyer_rel",
        "letter_id",
        "employee_id",
        string="Assigned Lawyers",
        domain=[("user_id.partner_id.is_lawyer", "=", True)],
    )
    lawyer_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Lawyer",
        domain=[("user_id.partner_id.is_lawyer", "=", True)],
        compute="_compute_lawyer_employee_id",
        inverse="_inverse_lawyer_employee_id",
        store=True,
    )
    lawyer_user_id = fields.Many2one(
        "res.users",
        string="Assigned Lawyer User",
        related="lawyer_employee_id.user_id",
        store=True,
        readonly=True,
    )
    assigned_date = fields.Datetime(
        string="Assignment Date",
        copy=False,
        tracking=True,
    )
    kanban_assignment_date = fields.Datetime(
        string="Kanban Assignment Date",
        compute="_compute_kanban_assignment_date",
    )
    lawyer_cost_hour = fields.Monetary(
        string="Lawyer Cost Per Hour",
        currency_field="currency_id",
        readonly=True,
    )
    hourly_cost = fields.Monetary(
        string="Cost Per Hour",
        currency_field="currency_id",
        readonly=True,
    )
    planned_hours = fields.Float(string="Planned Hours")
    total_estimated_cost = fields.Monetary(
        string="Total Estimated Cost",
        currency_field="currency_id",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain=[("move_type", "=", "out_invoice")],
        copy=False,
    )
    invoice_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Invoice Status",
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        copy=False,
        ondelete="set null",
        tracking=True,
    )
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True,
    )
    payment_status = fields.Selection(
        selection=PAYMENT_STATUS_SELECTION,
        string="Payment Status",
        compute="_compute_payment_status",
        store=True,
        readonly=True,
    )
    services_description = fields.Text(string="Services Description")
    description = fields.Text(string="Project Description")
    payment_terms = fields.Char(string="Payment Terms")
    
    time_entry_ids = fields.One2many(
        "qlk.task",
        "engagement_id",
        string="Hours / Time Entries",
    )
    case_ids = fields.One2many("qlk.case", "engagement_id", string="Cases")
    pre_litigation_ids = fields.One2many(
        "qlk.pre.litigation", "engagement_id", string="Pre-Litigation"
    )
    corporate_case_ids = fields.One2many(
        "qlk.corporate.case", "engagement_id", string="Corporate Cases"
    )
    arbitration_case_ids = fields.One2many(
        "qlk.arbitration.case", "engagement_id", string="Arbitration Cases"
    )
    hours_logged_ok = fields.Boolean(
        string="Hours Logged?",
        compute="_compute_hours_logged_ok",
        store=True,
        default=False,
        help="Automatically toggled based on logging tasks/hours",
    )
    document_type = fields.Selection(
        selection=DOCUMENT_TYPE_SELECTION,
        string="Document Type",
        default="engagement_letter",
        tracking=True,
    )
    approval_role = fields.Selection(
        selection=[("manager", "Manager"), ("assistant_manager", "Assistant Manager")],
        string="Approval Role",
        required=True,
        tracking=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Approver (Deprecated)",
        compute="_compute_deprecated_approver_id",
        readonly=True,
    )
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True)
    manager_id = fields.Many2one(
        "res.users",
        string="Manager",
        compute="_compute_deprecated_approvers",
        readonly=True,
    )
    assistant_manager_id = fields.Many2one(
        "res.users",
        string="Assistant Manager",
        compute="_compute_deprecated_approvers",
        readonly=True,
    )
    can_approve = fields.Boolean(
        string="Can Approve",
        compute="_compute_can_approve",
    )

    # ------------------------------------------------------------------------------
    # توحيد حقل العميل مع الحقل القديم للحفاظ على التوافق مع بقية النظام.
    # ------------------------------------------------------------------------------
    @api.depends("partner_id")
    def _compute_client_id(self):
        for record in self:
            record.client_id = record.partner_id

    @api.depends("time_entry_ids")
    def _compute_hours_logged_ok(self):
        for record in self:
            record.hours_logged_ok = bool(record.time_entry_ids)

    @api.depends("assigned_date", "create_date")
    def _compute_kanban_assignment_date(self):
        for record in self:
            record.kanban_assignment_date = record.assigned_date or record.create_date

    @api.onchange("time_entry_ids")
    def _onchange_time_entry_ids(self):
        for record in self:
            record.hours_logged_ok = bool(record.time_entry_ids)

    def _inverse_client_id(self):
        for record in self:
            record.partner_id = record.client_id

    # ------------------------------------------------------------------------------
    # دالة تحسب الساعات السنوية بناءً على الإدخال الشهري.
    # ------------------------------------------------------------------------------
    @api.depends("monthly_corporate_hours")
    def _compute_yearly_hours(self):
        for letter in self:
            letter.yearly_hours = (letter.monthly_corporate_hours or 0.0) * 12.0

    @api.onchange("retainer_type", "engagement_type", "project_type")
    def _onchange_legacy_service_type(self):
        for letter in self:
            if letter.service_type:
                continue
            letter.service_type = letter._infer_service_type()

    def _infer_service_type(self):
        self.ensure_one()
        source = self.retainer_type or self.engagement_type or self.project_type or "corporate"
        if source in {"litigation_corporate", "management_litigation", "management_corporate"}:
            return "mixed"
        if source == "litigation":
            return "litigation"
        if source == "arbitration":
            return "arbitration"
        if source == "pre_litigation":
            return "pre_litigation"
        return "corporate"

    def _service_allows(self, service):
        self.ensure_one()
        if self.service_type == "mixed":
            return True
        return self.service_type == service

    @api.depends(
        "contract_type",
        "agreed_hours",
        "agreed_case_count",
        "case_ids.total_hours",
        "pre_litigation_ids.hours_used",
        "corporate_case_ids.actual_hours_total",
        "arbitration_case_ids.actual_hours_total",
    )
    def _compute_engagement_consumption(self):
        for letter in self:
            case_hours = sum(letter.case_ids.mapped("total_hours"))
            pre_hours = sum(letter.pre_litigation_ids.mapped("hours_used"))
            corporate_hours = sum(letter.corporate_case_ids.mapped("actual_hours_total"))
            arbitration_hours = sum(letter.arbitration_case_ids.mapped("actual_hours_total"))
            total_hours = round(case_hours + pre_hours + corporate_hours + arbitration_hours, 2)

            case_count = len(letter.case_ids)
            pre_count = len(letter.pre_litigation_ids)
            corporate_count = len(letter.corporate_case_ids)
            arbitration_count = len(letter.arbitration_case_ids)
            total_cases = case_count + pre_count + corporate_count + arbitration_count

            letter.total_hours_used = total_hours
            letter.case_count = case_count
            letter.pre_litigation_count = pre_count
            letter.corporate_count = corporate_count
            letter.arbitration_count = arbitration_count
            letter.total_cases = total_cases
            letter.remaining_cases = (letter.agreed_case_count or 0) - total_cases
            letter.over_consumed = (
                (letter.contract_type == "hours" and bool(letter.agreed_hours) and total_hours > letter.agreed_hours)
                or (
                    letter.contract_type == "cases"
                    and bool(letter.agreed_case_count)
                    and total_cases > letter.agreed_case_count
                )
            )
            letter.consumption_label = _("Over Consumed") if letter.over_consumed else False

    # ------------------------------------------------------------------------------
    # دالة تجمع مبالغ سطور الرسوم لإظهار الإجمالي في الهيدر.
    # ------------------------------------------------------------------------------
    @api.depends("total_legal_fees")
    def _compute_fee_total(self):
        for letter in self:
            letter.fee_total = letter.total_legal_fees

    @api.depends("proposal_id.total_legal_fees", "proposal_id.legal_fees")
    def _compute_proposal_legal_fee(self):
        for letter in self:
            letter.proposal_legal_fee = letter.proposal_id.total_legal_fees if letter.proposal_id else 0.0

    @api.depends("legal_fees_lines.subtotal", "legal_fee_amount", "billing_type")
    def _compute_total_fees(self):
        for letter in self:
            if letter.billing_type == "free":
                letter.total_legal_fees = 0.0
                continue
            lines_total = sum(letter.legal_fees_lines.mapped("subtotal"))
            letter.total_legal_fees = lines_total or (letter.legal_fee_amount or 0.0)

    @api.depends("total_legal_fees", "legal_fee_amount", "billing_type")
    def _compute_total_amount(self):
        for letter in self:
            if letter.billing_type == "free":
                letter.total_amount = 0.0
                continue
            letter.total_amount = letter.total_legal_fees or (letter.legal_fee_amount or 0.0)

    @api.depends(
        "billing_type",
        "retainer_period",
        "year_start_date",
        "year_end_date",
        "project_id",
    )
    def _compute_used_hours(self):
        self._compute_retainer_used_hours()

    @api.depends("billing_type", "allocated_hours", "used_hours", "contract_type", "agreed_hours", "total_hours_used")
    def _compute_remaining_hours(self):
        legacy_records = self.browse()
        for letter in self:
            if letter.contract_type == "hours":
                letter.remaining_hours = (letter.agreed_hours or 0.0) - (letter.total_hours_used or 0.0)
            else:
                legacy_records |= letter
        if legacy_records:
            legacy_records._compute_retainer_remaining_hours()

    @api.depends(
        "billing_type",
        "project_id",
    )
    def _compute_monthly_used_hours(self):
        self._compute_retainer_monthly_used_hours()

    @api.depends(
        "billing_type",
        "retainer_period",
        "allocated_hours",
        "monthly_hours_limit",
        "used_hours",
        "monthly_used_hours",
    )
    def _compute_retainer_usage_percent(self):
        self._compute_retainer_usage_visuals()

    
    @api.depends("invoice_id", "invoice_state")
    def _compute_payment_status(self):
        for letter in self:
            if not letter.invoice_id:
                letter.payment_status = "unpaid"
                continue
            if letter.invoice_state == "paid":
                letter.payment_status = "paid"
            elif letter.invoice_state == "partial":
                letter.payment_status = "partial"
            else:
                letter.payment_status = "unpaid"

    @api.depends("approval_role")
    def _compute_can_approve(self):
        user = self.env.user
        for record in self:
            if record.approval_role == "manager":
                record.can_approve = user.has_group("qlk_management.group_bd_manager")
            elif record.approval_role == "assistant_manager":
                record.can_approve = user.has_group("qlk_management.group_bd_manager")
            else:
                record.can_approve = False

    @api.depends("approval_role")
    def _compute_deprecated_approvers(self):
        for record in self:
            record.manager_id = False
            record.assistant_manager_id = False

    @api.depends("approved_by")
    def _compute_deprecated_approver_id(self):
        for record in self:
            record.approver_id = record.approved_by

    @api.model
    def _clean_invalid_links(self):
        records = self.sudo().search([])
        for name, field in self._fields.items():
            if field.type != "many2one":
                continue
            table = self._table
            column = name
            comodel = self.env.get(field.comodel_name)
            if not comodel:
                self.env.cr.execute(
                    f"""
                    SELECT id
                    FROM {table}
                    WHERE {column} IS NOT NULL
                    """
                )
                bad_ids = [row[0] for row in self.env.cr.fetchall()]
                if bad_ids:
                    records.browse(bad_ids).write({name: False})
                continue
            comodel_table = comodel._table
            self.env.cr.execute(
                f"""
                SELECT id
                FROM {table}
                WHERE {column} IS NOT NULL
                  AND {column} NOT IN (SELECT id FROM {comodel_table})
                """
            )
            bad_ids = [row[0] for row in self.env.cr.fetchall()]
            if bad_ids:
                records.browse(bad_ids).write({name: False})

    # ------------------------------------------------------------------------------
    # التحقق من الحالات قبل تغييرها لضمان صحة دورة العمل.
    # ------------------------------------------------------------------------------
    def _ensure_state(self, allowed_states):
        for letter in self:
            if letter.state not in allowed_states:
                raise UserError(
                    _("Invalid state transition. Allowed: %s. Current: %s")
                    % (", ".join(allowed_states), letter.state)
                )

    # ------------------------------------------------------------------------------
    # إرسال للموافقة (Draft -> Waiting Manager Approval).
    # ------------------------------------------------------------------------------
    def action_send_manager_approval(self):
        self._ensure_state({"draft"})
        for letter in self:
            letter.write(
                {
                    "rejection_reason": False,
                    "state": "waiting_manager_approval",
                }
            )
            if letter.reviewer_id:
                letter.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=letter.reviewer_id.id,
                    summary=_("Approve engagement letter %s") % (letter.code or ""),
                )

    # ------------------------------------------------------------------------------
    # موافقة المدير (Waiting Manager Approval -> Approved by Manager).
    # ------------------------------------------------------------------------------
    def action_manager_approve(self):
        self._ensure_state({"waiting_manager_approval"})
        for letter in self:
            letter._check_approval_rights()
            letter.write(
                {
                    "approved_by": self.env.user.id,
                    "state": "approved_manager",
                }
            )
            letter.message_post(body=_("Manager approved. Ready to send to client."))

    # ------------------------------------------------------------------------------
    # إرسال لموافقة العميل (Approved by Manager -> Waiting Client Approval).
    # ------------------------------------------------------------------------------
    def action_send_client_approval(self):
        self._ensure_state({"approved_manager"})
        for letter in self:
            letter._check_approval_rights()
            letter.write({"state": "waiting_client_approval"})
            letter.message_post(body=_("Engagement letter sent for client approval."))

    def action_send_for_approval(self):
        return self.action_send_manager_approval()

    def action_approve(self):
        return self.action_manager_approve()

    def _open_rejection_wizard(self, rejection_role):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rejection Reason"),
            "res_model": "bd.rejection.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("qlk_management.view_bd_rejection_wizard_form").id,
            "target": "new",
            "context": {
                "default_rejection_role": rejection_role,
                "active_model": self._name,
                "active_ids": self.ids,
            },
        }

    # ------------------------------------------------------------------------------
    # رفض المدير (Waiting Manager Approval/Approved by Manager -> Rejected).
    # ------------------------------------------------------------------------------
    def action_manager_reject(self):
        self.ensure_one()
        self._ensure_state({"waiting_manager_approval", "approved_manager"})
        for letter in self:
            letter._check_approval_rights()
        return self._open_rejection_wizard("manager")

    # ------------------------------------------------------------------------------
    # رفض العميل (Waiting Client Approval -> Rejected).
    # ------------------------------------------------------------------------------
    def action_client_reject(self):
        self.ensure_one()
        self._ensure_state({"waiting_client_approval"})
        for letter in self:
            letter._check_approval_rights()
        return self._open_rejection_wizard("client")

    def action_reject(self):
        return self.action_manager_reject()

    def _apply_rejection_reason(self, reason, rejection_role):
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Please provide the rejection reason before rejecting."))
        allowed = {"waiting_client_approval"} if rejection_role == "client" else {
            "waiting_manager_approval",
            "approved_manager",
        }
        self._ensure_state(allowed)
        for letter in self:
            letter._check_approval_rights()
            letter.write(
                {
                    "rejection_reason": reason,
                    "state": "rejected",
                }
            )
            letter.message_post(body=_("Engagement Letter rejected: %s") % reason)

    # ------------------------------------------------------------------------------
    # موافقة العميل (Waiting Client Approval -> Approved by Client).
    # ------------------------------------------------------------------------------
    def action_client_approve(self):
        self._ensure_state({"waiting_client_approval"})
        for letter in self:
            letter._check_approval_rights()
            letter.with_context(skip_hours_check=True).write(
                {
                    "approved_by": self.env.user.id,
                    "state": "approved_client",
                }
            )
            letter.message_post(body=_("Client approved the engagement letter."))

    # ------------------------------------------------------------------------------
    # زر لإرجاع السجل إلى المسودة بعد الرفض لمراجعة البيانات.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        self._ensure_state({"rejected", "cancelled"})
        for letter in self:
            letter.write(
                {
                    "rejection_reason": False,
                    "state": "draft",
                }
            )

    # ------------------------------------------------------------------------------
    # زر الطباعة يستخدم تقرير QWeb بعد التأكد من حالة الموافقة.
    # ------------------------------------------------------------------------------
    def action_print_excel(self):
        return self.env.ref("qlk_management.action_bd_engagement_letter_xlsx_report").report_action(self)

    def action_open_report_wizard(self):
        self.ensure_one()
        action = self.env.ref("qlk_management.action_bd_report_wizard").read()[0]
        action["context"] = {
            "default_record_type": "engagement",
            "default_date_from": self.date or fields.Date.context_today(self),
            "default_date_to": self.date or fields.Date.context_today(self),
        }
        return action

    def action_print_letter(self):
        for letter in self:
            if letter.state != "approved_client":
                raise UserError(_("Printing is allowed only after approval."))
        return self.env.ref("qlk_management.report_bd_engagement_letter").report_action(self)

    # ------------------------------------------------------------------------------
    # مراقبة رفع النسخة الموقعة لتوليد كود العميل تلقائياً.
    # ------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("partner_id") and vals.get("client_id"):
                vals["partner_id"] = vals["client_id"]
            if vals.get("lawyer_id"):
                lawyer_cost = self._get_lawyer_cost(vals["lawyer_id"])
                vals["hourly_cost"] = lawyer_cost
                vals["lawyer_cost_hour"] = lawyer_cost
            partner_id = vals.get("partner_id")
            partner = partner_id and self.env["res.partner"].browse(partner_id) or False
            if partner:
                partner_code = partner._get_client_code()
                vals.setdefault("client_code", partner_code)
                if not vals.get("code") or vals["code"] == "/":
                    vals["code"] = self._generate_letter_code(partner, partner_code)
        records = super().create(vals_list)
        records._sync_assigned_date()
        records._copy_partner_attachments()
        records._sync_partner_identity()
        records.with_context(skip_proposal_sync=True)._sync_proposal_financials()
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # records._check_hours_logged()
        return records

    def _copy_partner_attachments(self):
        Attachment = self.env["ir.attachment"].sudo()
        partners = self.mapped("partner_id")
        if not partners:
            return
        partner_attachments = Attachment.search(
            [("res_model", "=", "res.partner"), ("res_id", "in", partners.ids)]
        )
        attachments_by_partner = {}
        for attachment in partner_attachments:
            attachments_by_partner.setdefault(attachment.res_id, []).append(attachment)
        for letter in self:
            partner = letter.partner_id
            if not partner:
                continue
            for attachment in attachments_by_partner.get(partner.id, []):
                attachment.copy(
                    {
                        "res_model": letter._name,
                        "res_id": letter.id,
                    }
                )

    def write(self, vals):
        vals = dict(vals)
        if "translation_attachment_ids" in vals and "translation_status" not in vals:
            vals["translation_status"] = "draft"
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # if self._has_new_task_command(vals.get("time_entry_ids")):
        #     return super().write(vals)
        # if self._requires_new_task_on_write(vals):
        #     self._raise_missing_hours_error()
        previous_assignments = None
        if (
            not self.env.context.get("skip_assignment_date_sync")
            and "assigned_date" not in vals
            and any(field in vals for field in ("lawyer_id", "lawyer_employee_id"))
        ):
            previous_assignments = {
                letter.id: letter._get_assignment_anchor() for letter in self
            }
        if "lawyer_id" in vals and vals["lawyer_id"]:
            lawyer_cost = self._get_lawyer_cost(vals["lawyer_id"])
            vals["hourly_cost"] = lawyer_cost
            vals["lawyer_cost_hour"] = lawyer_cost
        if self._has_locked_financial_changes(vals):
            for letter in self:
                if letter.state == "approved_client":
                    raise UserError(_("Financial fields are locked after client approval."))
        res = super().write(vals)
        if previous_assignments is not None:
            self._sync_assigned_date(previous_assignments)
        if "partner_id" in vals:
            self._sync_partner_identity()
        if not self.env.context.get("skip_proposal_sync") and ("proposal_id" in vals or "legal_fee_amount" in vals):
            self._sync_proposal_financials()
        if any(field in vals for field in ("signed_document_id", "signed_document_ids", "state")):
            for letter in self:
                if (
                    letter.state == "approved_client"
                    and (letter.signed_document_ids or letter.signed_document_id)
                    and not letter.client_code_generated
                ):
                    letter._generate_client_code()
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # self._check_hours_logged()
        return res

    def _has_locked_financial_changes(self, vals):
        financial_fields = (
            "legal_fees_lines",
            "currency_id",
            "billing_type",
            "retainer_period",
            "allocated_hours",
            "monthly_hours_limit",
            "year_start_date",
            "year_end_date",
        )
        changed_fields = [field_name for field_name in financial_fields if field_name in vals]
        if not changed_fields:
            return False
        for letter in self:
            for field_name in changed_fields:
                field = letter._fields.get(field_name)
                if not field:
                    continue
                if field.type in {"one2many", "many2many"}:
                    return True
                current_value = letter[field_name]
                new_value = vals[field_name]
                if field.type == "many2one":
                    if (current_value.id or False) != (new_value or False):
                        return True
                else:
                    if current_value != new_value:
                        return True
        return False

    def _raise_missing_hours_error(self):
        model_label = self._description or self._name
        raise UserError(
            _(
                "⚠️ يجب إدخال الساعات قبل حفظ السجل في %(model)s.\n"
                "⚠️ Hours must be logged before saving this %(model)s."
            )
            % {"model": model_label}
        )

    def _check_hours_logged(self):
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        return
        if self.env.context.get("skip_hours_check"):
            return
        Task = self.env["qlk.task"]
        for record in self:
            if not Task.search_count([("engagement_id", "=", record.id)]):
                record._raise_missing_hours_error()

    def _requires_new_task_on_write(self, vals):
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        return False
        if self.env.context.get("skip_hours_check"):
            return False
        fields_changed = set(vals) - {"time_entry_ids"}
        if not fields_changed:
            return False
        return not self._has_new_task_command(vals.get("time_entry_ids"))

    @staticmethod
    def _has_new_task_command(commands):
        for command in commands or []:
            if isinstance(command, (list, tuple)) and command and command[0] == 0:
                return True
        return False

    @api.onchange("partner_id")
    def _onchange_partner_id_identity(self):
        self._sync_partner_identity()

    @api.onchange("lawyer_id")
    def _onchange_lawyer_id(self):
        for letter in self:
            if not letter.lawyer_id:
                continue
            cost, found = letter._find_lawyer_cost(letter.lawyer_id.id)
            if found:
                letter.lawyer_cost_hour = cost
                letter.hourly_cost = cost
            else:
                letter.lawyer_cost_hour = 0.0
                letter.hourly_cost = 0.0
                raise UserError(_("Cost calculation missing for this lawyer!"))

    @api.onchange("client_id")
    def _onchange_client_id(self):
        for letter in self:
            if letter.client_id:
                letter.partner_id = letter.client_id

    def _sync_partner_identity(self):
        for letter in self:
            partner = letter.partner_id
            if not partner:
                continue
            contact_details = partner._display_address() or ""
            letter.contact_details = contact_details

    def _sync_proposal_financials(self):
        for letter in self:
            if not letter.proposal_id:
                continue
            proposal = letter.proposal_id
            vals = {
                "legal_fee_amount": proposal.total_legal_fees or proposal.legal_fees or 0.0,
                "approval_role": proposal.approval_role,
                "lawyer_id": proposal.lawyer_id.id if proposal.lawyer_id else False,
                "lawyer_employee_id": proposal.lawyer_employee_id.id if proposal.lawyer_employee_id else False,
                "lawyer_ids": [(6, 0, proposal.lawyer_ids.ids)] if proposal.lawyer_ids else False,
                "lawyer_cost_hour": proposal.lawyer_cost_hour,
                "hourly_cost": proposal.hourly_cost,
                "planned_hours": proposal.planned_hours,
                "estimated_hours": proposal.planned_hours,
                "total_estimated_cost": proposal.total_estimated_cost,
                "billing_type": proposal.billing_type,
                "retainer_period": proposal.retainer_period,
                "allocated_hours": proposal.allocated_hours,
                "monthly_hours_limit": proposal.monthly_hours_limit,
                "year_start_date": proposal.year_start_date,
                "year_end_date": proposal.year_end_date,
                "exception_approved": proposal.exception_approved,
                "project_id": proposal.project_id.id,
                "scope_of_work": proposal.scope_of_work,
            }
            if proposal.legal_fees_lines:
                vals["legal_fees_lines"] = [(5, 0, 0)] + [
                    (
                        0,
                        0,
                        {
                            "service_name": line.service_name,
                            "description": line.description,
                            "service_type": line.service_type,
                            "assigned_lawyer_id": line.assigned_lawyer_id.id,
                            "quantity": line.quantity,
                            "unit_price": line.unit_price,
                            "discount_type": line.discount_type,
                            "discount": line.discount,
                            "lawyer_cost": line.lawyer_cost,
                            "amount": line.amount,
                            "due_date": line.due_date,
                        },
                    )
                    for line in proposal.legal_fees_lines
                ]
            else:
                vals["legal_fees_lines"] = [(5, 0, 0)]
            letter.with_context(skip_proposal_sync=True).write(vals)

    def _sync_client_code_from_partner(self):
        for letter in self:
            if not letter.partner_id:
                continue
            client_code = letter.partner_id.code or letter.partner_id.ref or ""
            code = letter.code or ""
            if code and "/EL" in code:
                suffix = code.split("/EL", 1)[1]
                code = f"{client_code}/EL{suffix}" if suffix else code
            elif client_code:
                code = letter._generate_letter_code(letter.partner_id, client_code)
            letter.write({"client_code": client_code, "code": code})

    def _find_lawyer_cost(self, lawyer_id):
        cost = self.env["lawyer.cost.calculation"].search([("partner_id", "=", lawyer_id)], limit=1)
        if cost:
            return cost.cost_per_hour, True
        employee_model = self.env["hr.employee"]
        domain_parts = []
        if "address_home_id" in employee_model._fields:
            domain_parts.append(("address_home_id", "=", lawyer_id))
        if "work_contact_id" in employee_model._fields:
            domain_parts.append(("work_contact_id", "=", lawyer_id))
        if "user_id" in employee_model._fields:
            domain_parts.append(("user_id.partner_id", "=", lawyer_id))
        if domain_parts:
            employee_domain = []
            for part in domain_parts:
                if employee_domain:
                    employee_domain = ["|"] + employee_domain + [part]
                else:
                    employee_domain = [part]
            employees = employee_model.search(employee_domain)
            if employees:
                cost = self.env["cost.calculation"].search(
                    [("employee_id", "in", employees.ids)], limit=1
                )
                if cost:
                    return cost.cost_per_hour, True
        return 0.0, False

    def _employee_from_partner(self, partner):
        if not partner:
            return self.env["hr.employee"]
        employee_model = self.env["hr.employee"]
        domain_parts = []
        if "address_home_id" in employee_model._fields:
            domain_parts.append(("address_home_id", "=", partner.id))
        if "work_contact_id" in employee_model._fields:
            domain_parts.append(("work_contact_id", "=", partner.id))
        if "user_id" in employee_model._fields:
            domain_parts.append(("user_id.partner_id", "=", partner.id))
        if not domain_parts:
            return employee_model.browse()
        employee_domain = []
        for part in domain_parts:
            if employee_domain:
                employee_domain = ["|"] + employee_domain + [part]
            else:
                employee_domain = [part]
        return employee_model.search(employee_domain, limit=1)

    def _partner_from_employee(self, employee):
        if not employee:
            return self.env["res.partner"]
        if employee.user_id and employee.user_id.partner_id:
            return employee.user_id.partner_id
        if "work_contact_id" in employee._fields and employee.work_contact_id:
            return employee.work_contact_id
        if "address_home_id" in employee._fields and employee.address_home_id:
            return employee.address_home_id
        return self.env["res.partner"]

    def _get_assignment_anchor(self):
        self.ensure_one()
        if self.lawyer_employee_id:
            return self.lawyer_employee_id.id
        return self._employee_from_partner(self.lawyer_id).id or False

    def _sync_assigned_date(self, previous_assignments=None):
        if self.env.context.get("skip_assignment_date_sync"):
            return
        now = fields.Datetime.now()
        for record in self:
            current_assignment = record._get_assignment_anchor()
            if previous_assignments is None:
                if current_assignment and not record.assigned_date:
                    record.with_context(skip_assignment_date_sync=True).write(
                        {"assigned_date": now}
                    )
                continue
            previous_assignment = previous_assignments.get(record.id)
            if previous_assignment != current_assignment:
                record.with_context(skip_assignment_date_sync=True).write(
                    {"assigned_date": now if current_assignment else False}
                )

    @api.depends("lawyer_id")
    def _compute_lawyer_employee_id(self):
        for record in self:
            record.lawyer_employee_id = record._employee_from_partner(record.lawyer_id)

    def _inverse_lawyer_employee_id(self):
        for record in self:
            partner = record._partner_from_employee(record.lawyer_employee_id)
            record.lawyer_id = partner.id if partner else False

    @api.onchange("lawyer_employee_id")
    def _onchange_lawyer_employee_id(self):
        for record in self:
            partner = record._partner_from_employee(record.lawyer_employee_id)
            record.lawyer_id = partner.id if partner else False
            if not record.lawyer_id:
                record.lawyer_cost_hour = 0.0
                record.hourly_cost = 0.0
                continue
            cost, found = record._find_lawyer_cost(record.lawyer_id.id)
            if found:
                record.lawyer_cost_hour = cost
                record.hourly_cost = cost
            else:
                record.lawyer_cost_hour = 0.0
                record.hourly_cost = 0.0
                raise UserError(_("Cost calculation missing for this lawyer!"))

    def _get_lawyer_cost(self, lawyer_id):
        cost, _found = self._find_lawyer_cost(lawyer_id)
        return cost

    # ------------------------------------------------------------------------------
    # بعد الموافقة ورفع النسخة الموقعة يتم إنشاء client_code بصيغة C-2025-0001.
    # ------------------------------------------------------------------------------
    def _generate_client_code(self):
        for letter in self:
            if not letter.partner_id:
                continue
            if letter.partner_id.bd_client_code:
                letter.client_code_generated = True
                continue
            code = self.env["ir.sequence"].next_by_code("bd.client.code")
            if not code:
                raise UserError(_("Client code sequence is missing."))
            letter.partner_id.sudo().bd_client_code = code
            letter.client_code_generated = True
            letter.signed_on = fields.Datetime.now()
            letter.message_post(body=_("Client code %s generated for %s") % (code, letter.partner_id.display_name))

    def _generate_letter_code(self, partner, partner_code):
        prefix = f"{partner_code}/EL"
        last_letter = self.env["bd.engagement.letter"].with_context(active_test=False).search(
            [("partner_id", "=", partner.id), ("code", "like", f"{prefix}%")],
            order="code desc",
            limit=1,
        )
        next_number = 1
        if last_letter and last_letter.code:
            try:
                next_number = int(last_letter.code.split("EL")[-1]) + 1
            except (ValueError, IndexError):
                next_number = 1
        return f"{prefix}{next_number:03d}"

    def action_create_invoice(self):
        self.ensure_one()
        if not self._is_invoice_billing():
            raise UserError(_("Invoices are only required for paid engagements."))
        if self.invoice_id:
            raise UserError(_("An invoice has already been created for this engagement letter."))
        if not self.partner_id:
            raise UserError(_("Please select a client before creating the invoice."))
        if not self.total_amount:
            raise UserError(_("Please set the service amount before creating the invoice."))

        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company_id.id)], limit=1
        )
        if not journal:
            raise UserError(_("Please configure a sales journal for the company."))

        income_account = self.env["account.account"].search(
            [
                ("company_ids", "in", self.company_id.id),
                ("account_type", "in", ("income", "income_other")),
            ],
            limit=1,
        )
        if not income_account:
            raise UserError(_("Please configure a sales account to create invoices."))

        invoice_lines = [
            (
                0,
                0,
                {
                    "name": line.service_name or line.description or _("Legal Fees"),
                    "quantity": line.quantity or 1.0,
                    # Keep invoice pricing aligned with the document currency and pricing model.
                    "price_unit": (
                        (line.subtotal / (line.quantity or 1.0))
                        if line.discount_type == "fixed"
                        else (line.unit_price or 0.0)
                    ),
                    "discount": line.discount if line.discount_type == "percent" else 0.0,
                    "account_id": income_account.id,
                },
            )
            for line in self.legal_fees_lines
        ]
        if not invoice_lines:
            invoice_lines = [
                (
                    0,
                    0,
                    {
                        "name": _("Engagement Letter Services"),
                        "quantity": 1.0,
                        "price_unit": self.total_amount,
                        "account_id": income_account.id,
                    },
                )
            ]

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.code or "",
            "invoice_line_ids": invoice_lines,
            "journal_id": journal.id,
        }

        invoice = self.env["account.move"].create(move_vals)
        self.invoice_id = invoice.id

        return {
            "type": "ir.actions.act_window",
            "name": _("Invoice"),
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_case(self):
        self.ensure_one()
        if self.state != "approved_client":
            raise UserError(_("Only approved engagement letters can create cases."))
        if not self._service_allows("litigation"):
            raise UserError(_("This engagement letter does not allow litigation case creation."))
        degree = self.litigation_degree_ids[:1]
        if not degree:
            raise UserError(_("Select at least one allowed litigation degree before creating a case."))
        if self.contract_type == "cases" and self.agreed_case_count and self.remaining_cases <= 0:
            raise UserError(_("Case limit exceeded for this engagement letter."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Case"),
            "res_model": "qlk.case",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_engagement_id": self.id,
                "default_client_id": self.partner_id.id,
                "default_client_ids": self.partner_id.ids,
                "default_employee_id": self.lawyer_employee_id.id,
                "default_litigation_degree_id": degree.id,
                "default_litigation_level_id": degree.level_id.id,
                "default_litigation_flow": "litigation",
            },
        }

    def action_create_project(self):
        self.ensure_one()
        self.env["project.project"]._ensure_legal_manager()
        if self.state != "approved_client":
            raise UserError(_("Only approved engagement letters can create projects."))
        if not self.partner_id:
            raise UserError(_("Please select a client before creating a project."))
        if self.project_id:
            raise UserError(_("A project has already been created for this engagement letter."))
        existing_project = self.env["project.project"].search(
            [("engagement_letter_id", "=", self.id)],
            limit=1,
        )
        if existing_project:
            self.project_id = existing_project.id
            raise UserError(_("A project has already been created for this engagement letter."))
        service_type = self.env["project.project"]._get_service_type_from_engagement(self)
        if not service_type:
            raise UserError(_("Select a specific legal service type before creating a project."))

        project = self.env["project.project"].create(
            {
                "name": self.code or _("Engagement Project"),
                "client_id": self.partner_id.id,
                "engagement_letter_id": self.id,
                "service_type": service_type,
                "contract_type": self.contract_type,
                "lawyer_id": self.lawyer_employee_id.id,
                "company_id": self.company_id.id,
                "legal_fee_amount": self.legal_fee_amount or self.total_amount,
                "engagement_reference": self.code,
                "billing_type": self.billing_type,
                "retainer_type": self.retainer_type,
                "fee_structure": self.fee_structure,
                "payment_terms": self.payment_terms,
            }
        )
        self.project_id = project.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "project.project",
            "res_id": project.id,
            "view_mode": "form",
            "target": "current",
        }

    def _action_open_related_records(self, model_name, domain, name):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_engagement_id": self.id},
        }

    def action_open_cases(self):
        self.ensure_one()
        return self._action_open_related_records("qlk.case", [("engagement_id", "=", self.id)], _("Cases"))

    def action_open_pre_litigation(self):
        self.ensure_one()
        return self._action_open_related_records(
            "qlk.pre.litigation", [("engagement_id", "=", self.id)], _("Pre-Litigation")
        )

    def action_open_corporate_cases(self):
        self.ensure_one()
        return self._action_open_related_records(
            "qlk.corporate.case", [("engagement_id", "=", self.id)], _("Corporate")
        )

    def action_open_arbitration_cases(self):
        self.ensure_one()
        return self._action_open_related_records(
            "qlk.arbitration.case", [("engagement_id", "=", self.id)], _("Arbitration")
        )

    def action_view_client_attachments(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError(_("Please select a client before opening attachments."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Client Documents"),
            "res_model": "qlk.client.document",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", partner.id)],
            "context": {
                "default_partner_id": partner.id,
                "default_related_model": self._name,
                "default_related_res_id": self.id,
            },
        }
    
    def _check_approval_rights(self):
        for letter in self:
            if letter.approval_role == "manager" and not self.env.user.has_group(
                "qlk_management.group_bd_manager"
            ):
                raise UserError(_("Only Managers can approve or reject this document."))
            if letter.approval_role == "assistant_manager" and not self.env.user.has_group(
                "qlk_management.group_bd_manager"
            ):
                raise UserError(_("Only Assistant Managers can approve or reject this document."))

    @api.model
    def cron_check_retainer_usage(self):
        letters = self.search(
            [
                ("billing_type", "!=", "free"),
                ("retainer_period", "!=", False),
                ("state", "not in", ("rejected", "cancelled")),
            ]
        )
        letters._process_retainer_notifications()


class BDEngagementLetterFee(models.Model):
    _name = "bd.engagement.letter.fee"
    _description = "Engagement Letter Fee Line"

    letter_id = fields.Many2one(
        "bd.engagement.letter", string="Engagement Letter", required=True, ondelete="cascade", index=True
    )
    service_name = fields.Char(string="Service Name")
    description = fields.Char(string="Description")
    service_type = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("litigation_corporate", "Litigation + Corporate"),
            ("management_corporate", "Management Corporate"),
            ("management_litigation", "Management Litigation"),
        ],
        string="Service Type",
    )
    assigned_lawyer_id = fields.Many2one(
        "hr.employee",
        string="Assigned Lawyer",
        domain=[("user_id.partner_id.is_lawyer", "=", True)],
        index=True,
    )
    quantity = fields.Float(string="Quantity", default=1.0)
    unit_price = fields.Monetary(string="Unit Price")
    discount_type = fields.Selection(
        [("fixed", "Fixed"), ("percent", "Percentage")],
        string="Discount Type",
        default="fixed",
    )
    discount = fields.Float(string="Discount")
    lawyer_cost = fields.Monetary(
        string="Lawyer Cost",
        currency_field="currency_id",
        copy=False,
        help="Frozen lawyer cost captured when the line lawyer is selected.",
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_subtotal",
        store=True,
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
    )
    due_date = fields.Date(string="Due Date")
    currency_id = fields.Many2one(
        related="letter_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )

    @api.depends("quantity", "unit_price", "discount", "discount_type", "amount")
    def _compute_subtotal(self):
        for line in self:
            if not line.unit_price and not line.discount and line.amount:
                line.subtotal = line.amount
                continue
            gross_amount = (line.quantity or 0.0) * (line.unit_price or 0.0)
            if line.discount_type == "percent":
                discount_amount = gross_amount * ((line.discount or 0.0) / 100.0)
            else:
                discount_amount = line.discount or 0.0
            line.subtotal = gross_amount - discount_amount

    def _get_line_subtotal_from_vals(self, vals):
        record = self[:1]
        quantity = vals.get("quantity", record.quantity or 0.0)
        unit_price = vals.get("unit_price", record.unit_price or 0.0)
        discount = vals.get("discount", record.discount or 0.0)
        discount_type = vals.get("discount_type", record.discount_type or "fixed")
        gross_amount = (quantity or 0.0) * (unit_price or 0.0)
        if discount_type == "percent":
            discount_amount = gross_amount * ((discount or 0.0) / 100.0)
        else:
            discount_amount = discount or 0.0
        return gross_amount - discount_amount

    def _get_current_lawyer_cost(self, employee):
        if not employee:
            return 0.0
        if employee.lawyer_hour_cost:
            return employee.lawyer_hour_cost
        partner = employee.user_id.partner_id or employee.work_contact_id or employee.address_home_id
        if not partner:
            return 0.0
        cost_record = self.env["lawyer.cost.calculation"].search(
            [("partner_id", "=", partner.id)],
            limit=1,
        )
        return cost_record.cost_per_hour if cost_record else 0.0

    def _normalize_line_vals(self, vals):
        if vals.get("service_name") and not vals.get("description"):
            vals["description"] = vals["service_name"]
        elif vals.get("description") and not vals.get("service_name"):
            vals["service_name"] = vals["description"]
        if vals.get("assigned_lawyer_id") and "lawyer_cost" not in vals:
            employee = self.env["hr.employee"].browse(vals["assigned_lawyer_id"])
            vals["lawyer_cost"] = self._get_current_lawyer_cost(employee)
        pricing_keys = {"quantity", "unit_price", "discount", "discount_type"}
        if pricing_keys.intersection(vals):
            vals["amount"] = self._get_line_subtotal_from_vals(vals)
        return vals

    @api.onchange("assigned_lawyer_id")
    def _onchange_assigned_lawyer_id(self):
        for line in self:
            if line.assigned_lawyer_id and not line.lawyer_cost:
                line.lawyer_cost = line._get_current_lawyer_cost(line.assigned_lawyer_id)

    @api.onchange("service_name", "quantity", "unit_price", "discount", "discount_type")
    def _onchange_pricing_fields(self):
        for line in self:
            if line.service_name and not line.description:
                line.description = line.service_name
            line.amount = line._get_line_subtotal_from_vals({})

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_line_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        pricing_keys = {"quantity", "unit_price", "discount", "discount_type"}
        if len(self) > 1 and pricing_keys.intersection(vals):
            result = True
            for line in self:
                result = super(BDEngagementLetterFee, line).write(
                    line._normalize_line_vals(dict(vals))
                ) and result
            return result
        vals = self._normalize_line_vals(dict(vals))
        if "assigned_lawyer_id" in vals and "lawyer_cost" not in vals:
            if vals.get("assigned_lawyer_id"):
                employee = self.env["hr.employee"].browse(vals["assigned_lawyer_id"])
                vals["lawyer_cost"] = self._get_current_lawyer_cost(employee)
            else:
                vals["lawyer_cost"] = 0.0
        return super().write(vals)
