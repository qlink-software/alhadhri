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
    _inherit = ["mail.thread", "mail.activity.mixin", "qlk.notification.mixin"]
    _order = "create_date desc"
    _rec_name = "code"

    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
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
        [
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("litigation_corporate", "Litigation + Corporate"),
            ("litigation_arbitration", "Litigation + Arbitration"),
            ("corporate_arbitration", "Corporate + Arbitration"),
            ("litigation_corporate_arbitration", "Litigation + Corporate + Arbitration"),
        ],
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
    client_document_ids = fields.One2many(
        related="partner_id.client_document_ids",
        string="Client Documents",
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
    billing_type = fields.Selection(
        [("free", "Pro bono"), ("billable", "Paid")],
        string="Billing Type",
        default="billable",
        tracking=True,
    )
    allow_project_without_payment = fields.Boolean(
        string="Allow Project Before Payment",
        default=False,
        tracking=True,
    )
    estimated_hours = fields.Float(string="Estimated Hours")
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
    lawyer_id = fields.Many2one("res.partner", string="Assigned Lawyer")
    lawyer_ids = fields.Many2many(
        "hr.employee",
        "bd_engagement_letter_lawyer_rel",
        "letter_id",
        "employee_id",
        string="Assigned Lawyers",
    )
    lawyer_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Lawyer",
        compute="_compute_lawyer_employee_id",
        inverse="_inverse_lawyer_employee_id",
        store=True,
    )
    lawyer_cost_hour = fields.Float(string="Lawyer Cost Per Hour", readonly=True)
    hourly_cost = fields.Float(string="Cost Per Hour", readonly=True)
    planned_hours = fields.Float(string="Planned Hours")
    total_estimated_cost = fields.Float(string="Total Estimated Cost")
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
    description = fields.Text(string="Project Description")
    payment_terms = fields.Char(string="Payment Terms")
    
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

    @api.depends("legal_fees_lines.amount", "legal_fee_amount", "billing_type")
    def _compute_total_amount(self):
        for letter in self:
            if letter.billing_type == "free":
                letter.total_amount = 0.0
                continue
            lines_total = sum(letter.legal_fees_lines.mapped("amount"))
            if lines_total:
                letter.total_amount = lines_total
            else:
                letter.total_amount = letter.legal_fee_amount or 0.0

    
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
        if any(field in vals for field in ("legal_fees_lines", "currency_id", "billing_type")):
            for letter in self:
                if letter.state in {"approved_manager", "waiting_client_approval", "approved_client"}:
                    raise UserError(_("Financial fields are locked after approval."))
        res = super().write(vals)
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

    @api.depends(
        "billing_type",
        "invoice_state",
        "invoice_id",
        "qlk_project_id",
        "state",
        "allow_project_without_payment",
    )
    def _compute_can_create_project(self):
        for letter in self:
            billing_ready = letter.billing_type == "free" or (
                letter.billing_type == "billable"
                and (
                    letter.allow_project_without_payment
                    or (letter.invoice_id and letter.invoice_state == "paid")
                )
            )
            eligible = letter.state == "approved_client" and billing_ready
            letter.can_create_project = bool(eligible and not letter.qlk_project_id)

    def action_create_invoice(self):
        self.ensure_one()
        if self.billing_type != "billable":
            raise UserError(_("Invoices are only required for billable engagements."))
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
                    "name": line.description or _("Legal Fees"),
                    "quantity": 1.0,
                    "price_unit": line.amount,
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

    def action_allow_project_without_payment(self):
        self.ensure_one()
        if not self.env.user.has_group("qlk_management.bd_manager_group"):
            raise UserError(_("Only Managers can allow project creation before payment."))
        if self.state != "approved_client":
            raise UserError(_("Only approved engagement letters can be exempted."))
        self.write({"allow_project_without_payment": True})

    def _ensure_project_creation_ready(self):
        for letter in self:
            if letter.qlk_project_id:
                raise UserError(_("A project has already been created for this engagement letter."))
            if letter.state != "approved_client":
                raise UserError(_("Only approved engagement letters can create projects."))
            if letter.billing_type == "billable":
                if not letter.invoice_id:
                    raise UserError(_("You must create an invoice before creating the project."))
                if not letter.allow_project_without_payment and letter.invoice_state != "paid":
                    raise UserError(_("The invoice must be fully paid before creating the project."))

    def _prepare_project_vals(self):
        self.ensure_one()
        partner = self.partner_id
        scope_note = self.description or self.services_description
        primary_employee = self.lawyer_employee_id
        if not primary_employee and self.lawyer_ids:
            primary_employee = self.lawyer_ids[:1]
        primary_partner = False
        if primary_employee:
            if primary_employee.user_id and primary_employee.user_id.partner_id:
                primary_partner = primary_employee.user_id.partner_id
            elif "work_contact_id" in primary_employee._fields and primary_employee.work_contact_id:
                primary_partner = primary_employee.work_contact_id
            elif "address_home_id" in primary_employee._fields and primary_employee.address_home_id:
                primary_partner = primary_employee.address_home_id
        return {
            "client_id": partner.id if partner else False,
            "engagement_id": self.id,
            "lawyer_id": primary_partner.id if primary_partner else False,
            "assigned_employee_ids": [(6, 0, self.lawyer_ids.ids)] if self.lawyer_ids else False,
            "lawyer_cost_hour": self.lawyer_cost_hour,
            "project_type": self.project_type or "corporate",
            "retainer_type": self.retainer_type or False,
            "company_id": self.company_id.id,
            "estimated_hours": self.planned_hours or self.estimated_hours or 0.0,
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
            "name": _("Client Documents"),
            "res_model": "qlk.client.document",
            "view_mode": "tree,form",
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
