# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# Engagement Letter (EL)
# هذا الموديل يمثل العقد الرسمي مع العميل ويتضمن منطق التسعير والساعات
# ونظام الموافقة والترقيم التلقائي مرهون بنوع العقد والسنة المالية.
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BDEngagementLetter(models.Model):
    _name = "bd.engagement.letter"
    _description = "Engagement Letter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Title", required=True, tracking=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    reference_number = fields.Char(string="Reference Number", readonly=True, copy=False)
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
    partner_qid = fields.Char(string="QID / ID")
    partner_passport = fields.Char(string="Passport")
    contact_details = fields.Text(string="Contact Details")
    fee_total = fields.Monetary(string="Fee Total", compute="_compute_fee_total", store=True)
    fee_line_ids = fields.One2many(
        "bd.engagement.letter.fee", "letter_id", string="Fee Breakdown"
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
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    comments = fields.Text(string="Comments")
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
    signed_on = fields.Datetime(string="Signed On", readonly=True)
    client_code_generated = fields.Boolean(string="Client Code Generated", readonly=True, copy=False)
    lawyer_id = fields.Many2one("hr.employee", string="Assigned Lawyer")
    hourly_cost = fields.Float(string="Cost Per Hour", readonly=True)
    planned_hours = fields.Float(string="Planned Hours")
    additional_cost = fields.Float(string="Additional Cost")
    total_estimated_cost = fields.Float(string="Total Estimated Cost")
    services_description = fields.Text(string="Services Description")
    project_scope = fields.Text(string="Project Scope")

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
        self._ensure_state({"draft", "rejected"})
        for letter in self:
            letter._assign_reference_number()
            letter.state = "waiting_approval"
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
        self._ensure_state({"waiting_approval"})
        for letter in self:
            letter.state = "approved"
            letter.message_post(body=_("Engagement Letter approved. Signed copy can be uploaded."))

    # ------------------------------------------------------------------------------
    # زر الرفض يعيد السجل إلى حالة rejected مع تسجيل الملاحظات.
    # ------------------------------------------------------------------------------
    def action_reject(self):
        self._ensure_state({"waiting_approval"})
        for letter in self:
            if not letter.comments:
                raise UserError(_("Please log the rejection reason in the comments field."))
            letter.state = "rejected"
            letter.message_post(body=_("Engagement Letter rejected: %s") % letter.comments)

    # ------------------------------------------------------------------------------
    # زر لإرجاع السجل إلى المسودة بعد الرفض لمراجعة البيانات.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        self._ensure_state({"rejected"})
        for letter in self:
            letter.state = "draft"

    # ------------------------------------------------------------------------------
    # زر الطباعة يستخدم تقرير QWeb بعد التأكد من حالة الموافقة.
    # ------------------------------------------------------------------------------
    def action_print_letter(self):
        for letter in self:
            if letter.state != "approved":
                raise UserError(_("Printing is allowed only after approval."))
        return self.env.ref("qlk_management.report_bd_engagement_letter").report_action(self)

    # ------------------------------------------------------------------------------
    # مراقبة رفع النسخة الموقعة لتوليد كود العميل تلقائياً.
    # ------------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        record = super().create(vals)
        record._sync_partner_identity()
        return record

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals:
            self._sync_partner_identity()
        if "signed_document_id" in vals or "state" in vals:
            for letter in self:
                if (
                    letter.state == "approved"
                    and letter.signed_document_id
                    and not letter.client_code_generated
                ):
                    letter._generate_client_code()
        return res

    @api.onchange("partner_id")
    def _onchange_partner_id_identity(self):
        self._sync_partner_identity()

    def _sync_partner_identity(self):
        for letter in self:
            partner = letter.partner_id
            if not partner:
                continue
            if partner.company_type == "person":
                details = partner.bd_contact_details or partner._display_address()
                letter.partner_qid = partner.bd_qid or partner.ref or ""
                letter.partner_passport = partner.bd_passport or ""
                letter.contact_details = details or ""
            else:
                if not letter.partner_qid and partner.bd_qid:
                    letter.partner_qid = partner.bd_qid
                if not letter.partner_passport and partner.bd_passport:
                    letter.partner_passport = partner.bd_passport
                if not letter.contact_details and partner.bd_contact_details:
                    letter.contact_details = partner.bd_contact_details

    # ------------------------------------------------------------------------------
    # زر إنشاء مشروع بعد موافقة العميل يقوم بإنشاء qlk.project وربطه بالاتفاقية.
    # ------------------------------------------------------------------------------
    # (project creation handled by qlk_project_management extension)

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
