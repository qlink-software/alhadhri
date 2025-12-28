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


class BDEngagementLetter(models.Model):
    _name = "bd.engagement.letter"
    _description = "Engagement Letter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Title", tracking=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    reference_number = fields.Char(string="Reference Number", readonly=True, copy=False)
    reference = fields.Char(string="Reference", tracking=True)
    code = fields.Char(string="Engagement Letter Code", default="/", copy=False, readonly=True)
    contract_type = fields.Selection(
        [("retainer", "Retainer"), ("lump_sum", "Lump Sum")],
        string="Contract Type",
        required=True,
        default="retainer",
        tracking=True,
    )
    retainer_type = fields.Selection(
        [("corporate", "Corporate"), ("litigation", "Litigation"), ("both", "Both")],
        string="Retainer Type",
        default="corporate",
        tracking=True,
    )
    monthly_corporate_hours = fields.Float(string="Monthly Corporate Hours")
    yearly_hours = fields.Float(
        string="Yearly Hours", compute="_compute_yearly_hours", store=True
    )
    litigation_cases_limit = fields.Integer(string="Litigation Cases Limit")
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True, tracking=True
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
    fee_total = fields.Monetary(string="Fee Total", compute="_compute_fee_total", store=True)
    fee_line_ids = fields.One2many(
        "bd.engagement.letter.fee", "letter_id", string="Fee Breakdown"
    )
    legal_fees_lines = fields.One2many(
        "bd.engagement.letter.fee",
        "letter_id",
        string="Legal Fees Lines",
    )
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
    fee_structure = fields.Char(string="Fee Structure")
    payment_terms = fields.Char(string="Payment Terms")
    legal_note = fields.Text(string="Legal Notes")
    legal_fee_amount = fields.Float(string="Legal Fees")
    proposal_legal_fee = fields.Float(
        string="Proposal Legal Fees",
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
    )
    rejection_reason = fields.Text(string="Rejection Reason")
    comments = fields.Text(string="Reason")
    # ------------------------------------------------------------------------------
    # يحتفظ بمرجع العرض الذي أنشأ هذه الاتفاقية لتسهيل التتبع وإعادة الفتح.
    # ------------------------------------------------------------------------------
    proposal_id = fields.Many2one("bd.proposal", string="Source Proposal", copy=False)
    opportunity_id = fields.Many2one("crm.lead", string="Opportunity", tracking=True)
    signed_document_id = fields.Many2one(
        "ir.attachment",
        string="Signed Copy",
        help="Upload the signed Engagement Letter after approval.",
        index=True,
    )
    signed_on = fields.Datetime(string="Signed On", readonly=True)
    client_code_generated = fields.Boolean(string="Client Code Generated", readonly=True, copy=False)
    lawyer_id = fields.Many2one("res.partner", string="Assigned Lawyer")
    lawyer_cost_hour = fields.Float(string="Lawyer Cost Per Hour", readonly=True)
    hourly_cost = fields.Float(string="Cost Per Hour", readonly=True)
    planned_hours = fields.Float(string="Planned Hours")
    total_estimated_cost = fields.Float(string="Total Estimated Cost")
    amount_total = fields.Monetary(string="Service Amount", currency_field="currency_id")
    billing_type = fields.Selection(
        [("paid", "Paid"), ("free", "Pro bono")],
        string="Billing Type",
        default="paid",
        tracking=True,
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
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    qlk_project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        readonly=True,
        copy=False,
        ondelete="set null",
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
    project_scope = fields.Text(string="Project Scope")
    description = fields.Text(string="Project Description")
    payment_terms = fields.Char(string="Payment Terms")
    collected_amount = fields.Float(string="Collected Amount", tracking=True, readonly=True)
    remaining_amount = fields.Float(
        string="Remaining Amount", compute="_compute_remaining_amount", store=True, readonly=True
    )
    time_entry_ids = fields.One2many(
        "qlk.task",
        "engagement_id",
        string="Hours / Time Entries",
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

    # ------------------------------------------------------------------------------
    # دالة تجمع مبالغ سطور الرسوم لإظهار الإجمالي في الهيدر.
    # ------------------------------------------------------------------------------
    @api.depends("fee_line_ids.amount")
    def _compute_fee_total(self):
        for letter in self:
            letter.fee_total = sum(letter.fee_line_ids.mapped("amount"))

    @api.depends("proposal_id.legal_fees")
    def _compute_proposal_legal_fee(self):
        for letter in self:
            letter.proposal_legal_fee = letter.proposal_id.legal_fees if letter.proposal_id else 0.0

    @api.depends("legal_fees_lines.amount", "amount_total", "legal_fee_amount")
    def _compute_total_amount(self):
        for letter in self:
            lines_total = sum(letter.legal_fees_lines.mapped("amount"))
            if lines_total:
                letter.total_amount = lines_total
            else:
                letter.total_amount = letter.amount_total or letter.legal_fee_amount or 0.0

    @api.depends("total_amount", "collected_amount")
    def _compute_remaining_amount(self):
        for letter in self:
            total = letter.total_amount or 0.0
            collected = letter.collected_amount or 0.0
            letter.remaining_amount = max(total - collected, 0.0)

    @api.depends("collected_amount", "total_amount")
    def _compute_payment_status(self):
        for letter in self:
            total = letter.total_amount or 0.0
            collected = letter.collected_amount or 0.0
            if total <= 0.0:
                letter.payment_status = "unpaid"
            elif collected >= total:
                letter.payment_status = "paid"
            elif collected > 0.0:
                letter.payment_status = "partial"
            else:
                letter.payment_status = "unpaid"

    @api.depends("approval_role")
    def _compute_can_approve(self):
        user = self.env.user
        for record in self:
            if record.approval_role == "manager":
                record.can_approve = user.has_group("qlk_management.bd_manager_group")
            elif record.approval_role == "assistant_manager":
                record.can_approve = user.has_group("qlk_management.bd_assistant_manager_group")
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
    # دالة داخلية لاستدعاء التسلسل المناسب بحسب نوع العقد.
    # ------------------------------------------------------------------------------
    def _get_reference_sequence(self):
        mapping = {
            "retainer": "bd.engagement.letter.retainer",
            "lump_sum": "bd.engagement.letter.lump_sum",
        }
        return mapping.get(self.contract_type, "bd.engagement.letter.retainer")

    # ------------------------------------------------------------------------------
    # Reference Format:
    # AH/EL/L/001/2025
    # AH ثابت، EL ثابت، TYPE حسب نوع العقد، SERIAL يبدأ من 001 لكل سنة.
    # ------------------------------------------------------------------------------
    def _assign_reference_number(self):
        for letter in self:
            if letter.reference_number:
                continue
            sequence_code = letter._get_reference_sequence()
            next_value = self.env["ir.sequence"].next_by_code(sequence_code)
            if not next_value:
                raise UserError(_("Sequence for engagement letter is not configured."))
            letter.reference_number = next_value

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
    # زر إرسال للموافقة ينقل السجل إلى waiting_approval ويولد المرجع تلقائياً.
    # ------------------------------------------------------------------------------
    def action_send_for_approval(self):
        self._ensure_state({"draft"})
        for letter in self:
            letter._assign_reference_number()
            letter.rejection_reason = False
            letter.state = "waiting_manager_approval"
            if letter.reviewer_id:
                letter.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=letter.reviewer_id.id,
                    summary=_("Approve engagement letter %s") % (letter.name or letter.reference_number),
                )

    # ------------------------------------------------------------------------------
    # زر الموافقة يحول السجل إلى approved ويتيح الطباعة ورفع النسخة الموقعة.
    # ------------------------------------------------------------------------------
    def action_approve(self):
        self._ensure_state({"waiting_manager_approval"})
        for letter in self:
            letter._check_approval_rights()
            letter.approved_by = self.env.user
            letter.state = "approved_manager"
            letter.message_post(body=_("Manager approved. Awaiting client approval."))
            letter.state = "waiting_client_approval"

    # ------------------------------------------------------------------------------
    # زر الرفض يعيد السجل إلى حالة rejected مع تسجيل الملاحظات.
    # ------------------------------------------------------------------------------
    def action_reject(self):
        self._ensure_state({"waiting_manager_approval"})
        for letter in self:
            letter._check_approval_rights()
            if not letter.rejection_reason:
                raise UserError(_("Please provide the rejection reason before rejecting."))
            letter.state = "rejected"
            letter.message_post(body=_("Engagement Letter rejected: %s") % letter.rejection_reason)

    def action_client_approve(self):
        self._ensure_state({"waiting_client_approval"})
        for letter in self:
            letter._check_approval_rights()
            project = letter.qlk_project_id
            if not project:
                project = letter._create_qlk_project_from_engagement()
            letter.with_context(skip_hours_check=True).write(
                {
                    "approved_by": self.env.user.id,
                    "state": "approved_client",
                    "qlk_project_id": project.id if project else False,
                }
            )
            letter.message_post(body=_("Client approved the engagement letter."))

    def action_client_reject(self):
        self._ensure_state({"waiting_client_approval"})
        for letter in self:
            letter._check_approval_rights()
            if not letter.rejection_reason:
                raise UserError(_("Please provide the rejection reason before rejecting."))
            letter.state = "rejected"
            letter.message_post(body=_("Client rejected the engagement letter: %s") % letter.rejection_reason)

    # ------------------------------------------------------------------------------
    # زر لإرجاع السجل إلى المسودة بعد الرفض لمراجعة البيانات.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        self._ensure_state({"rejected", "cancelled"})
        for letter in self:
            letter.rejection_reason = False
            letter.state = "draft"

    # ------------------------------------------------------------------------------
    # زر الطباعة يستخدم تقرير QWeb بعد التأكد من حالة الموافقة.
    # ------------------------------------------------------------------------------
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
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # if self._has_new_task_command(vals.get("time_entry_ids")):
        #     return super().write(vals)
        # if self._requires_new_task_on_write(vals):
        #     self._raise_missing_hours_error()
        if "lawyer_id" in vals and vals["lawyer_id"]:
            lawyer_cost = self._get_lawyer_cost(vals["lawyer_id"])
            vals["hourly_cost"] = lawyer_cost
            vals["lawyer_cost_hour"] = lawyer_cost
        if vals.get("state") == "approved_manager":
            vals["state"] = "waiting_client_approval"
        if any(field in vals for field in ("legal_fees_lines", "amount_total", "currency_id", "billing_type")):
            for letter in self:
                if letter.state in {"approved_manager", "waiting_client_approval", "approved_client"}:
                    raise UserError(_("Financial fields are locked after approval."))
        res = super().write(vals)
        if "partner_id" in vals:
            self._sync_partner_identity()
        if not self.env.context.get("skip_proposal_sync") and ("proposal_id" in vals or "legal_fee_amount" in vals):
            self._sync_proposal_financials()
        if "signed_document_id" in vals or "state" in vals:
            for letter in self:
                if (
                    letter.state == "approved_client"
                    and letter.signed_document_id
                    and not letter.client_code_generated
                ):
                    letter._generate_client_code()
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # self._check_hours_logged()
        return res

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
                "legal_fee_amount": proposal.legal_fees or 0.0,
                "engagement_type": proposal.engagement_type,
                "reference": proposal.reference,
                "approval_role": proposal.approval_role,
                "lawyer_id": proposal.lawyer_id.id if proposal.lawyer_id else False,
                "lawyer_cost_hour": proposal.lawyer_cost_hour,
                "hourly_cost": proposal.hourly_cost,
            }
            if proposal.legal_fees_lines:
                vals["legal_fees_lines"] = [(5, 0, 0)] + [
                    (0, 0, {"description": line.description, "amount": line.amount, "due_date": line.due_date})
                    for line in proposal.legal_fees_lines
                ]
            else:
                vals["legal_fees_lines"] = [(5, 0, 0)]
            letter.with_context(skip_proposal_sync=True).write(vals)

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

    def _get_lawyer_cost(self, lawyer_id):
        cost, _found = self._find_lawyer_cost(lawyer_id)
        return cost

    # ------------------------------------------------------------------------------
    # زر إنشاء مشروع بعد موافقة العميل يقوم بإنشاء qlk.project وربطه بالاتفاقية.
    # ------------------------------------------------------------------------------
    # (project creation is handled inside qlk_management)

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

    @api.depends("billing_type", "invoice_state", "invoice_id", "qlk_project_id", "state")
    def _compute_can_create_project(self):
        for letter in self:
            billing_ready = letter.billing_type == "free" or (
                letter.billing_type == "paid"
                and letter.invoice_id
                and letter.invoice_state == "paid"
            )
            eligible = letter.state == "approved_client" and billing_ready
            letter.can_create_project = bool(eligible and not letter.qlk_project_id)

    def action_create_invoice(self):
        self.ensure_one()
        if self.billing_type != "paid":
            raise UserError(_("Invoices are only required for paid engagements."))
        if self.invoice_id:
            raise UserError(_("An invoice has already been created for this engagement letter."))
        if not self.partner_id:
            raise UserError(_("Please select a client before creating the invoice."))
        if not self.amount_total:
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

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.reference_number or self.name,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": _("Engagement Letter Services"),
                        "quantity": 1.0,
                        "price_unit": self.amount_total,
                        "account_id": income_account.id,
                    },
                )
            ],
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

    def action_create_project(self):
        result_action = None
        for letter in self:
            letter._ensure_project_creation_ready()
            project = letter._create_qlk_project_from_engagement()
            letter.with_context(skip_hours_check=True).write({"qlk_project_id": project.id})
            result_action = letter._get_project_action(project.id)
        return result_action

    def action_open_project(self):
        self.ensure_one()
        if not self.qlk_project_id:
            raise UserError(_("No project has been created for this engagement letter yet."))
        return self._get_project_action(self.qlk_project_id.id)

    def _ensure_project_creation_ready(self):
        for letter in self:
            if letter.qlk_project_id:
                raise UserError(_("A project has already been created for this engagement letter."))
            if letter.state != "approved_client":
                raise UserError(_("Only approved engagement letters can create projects."))
            if letter.billing_type == "paid":
                if not letter.invoice_id:
                    raise UserError(_("You must create an invoice before creating the project."))
                if letter.invoice_state != "paid":
                    raise UserError(_("The invoice must be fully paid before creating the project."))

    def _prepare_project_vals(self):
        self.ensure_one()
        partner = self.partner_id
        scope_note = self.project_scope or self.description or self.services_description
        return {
            "client_id": partner.id if partner else False,
            "engagement_id": self.id,
            "lawyer_id": self.lawyer_id.id if self.lawyer_id else False,
            "lawyer_cost_hour": self.lawyer_cost_hour,
            "collected_amount": self.collected_amount,
            "remaining_amount": self.remaining_amount,
            "project_type": self.project_type or "corporate",
            "company_id": self.company_id.id,
            "description": scope_note,
        }

    def _get_project_action(self, project_id):
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "qlk.project",
            "res_id": project_id,
            "view_mode": "form",
            "target": "current",
        }

    def _create_qlk_project_from_engagement(self):
        self.ensure_one()
        project_vals = self._prepare_project_vals()
        fee_lines = [
            (0, 0, {"description": line.description, "amount": line.amount, "due_date": line.due_date})
            for line in self.legal_fees_lines
        ]
        if fee_lines:
            project_vals["legal_fee_line_ids"] = fee_lines
        project = self.env["qlk.project"].create(project_vals)
        tasks = self.env["qlk.task"].search([("engagement_id", "=", self.id)])
        if tasks:
            tasks.write({"engagement_id": False, "project_id": project.id})
        return project

    def action_view_client_attachments(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError(_("Please select a client before opening attachments."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Client Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "tree,form",
            "domain": [("res_model", "=", "res.partner"), ("res_id", "=", partner.id)],
            "context": {
                "default_res_model": "res.partner",
                "default_res_id": partner.id,
            },
        }
    
    def _check_approval_rights(self):
        for letter in self:
            if letter.approval_role == "manager" and not self.env.user.has_group(
                "qlk_management.bd_manager_group"
            ):
                raise UserError(_("Only Managers can approve or reject this document."))
            if letter.approval_role == "assistant_manager" and not self.env.user.has_group(
                "qlk_management.bd_assistant_manager_group"
            ):
                raise UserError(_("Only Assistant Managers can approve or reject this document."))


class BDEngagementLetterFee(models.Model):
    _name = "bd.engagement.letter.fee"
    _description = "Engagement Letter Fee Line"

    letter_id = fields.Many2one(
        "bd.engagement.letter", string="Engagement Letter", required=True, ondelete="cascade", index=True
    )
    description = fields.Char(string="Description", required=True)
    amount = fields.Monetary(string="Amount", required=True)
    due_date = fields.Date(string="Due Date")
    currency_id = fields.Many2one(
        related="letter_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )
