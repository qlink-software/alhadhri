# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديل العروض (Business Proposal)
# يقوم هذا الموديل بإدارة دورة حياة العرض من الإنشاء وحتى موافقة العميل.
# يغطي إنشاء العرض، إرسال الموافقة، الرفض مع الأسباب، وإعادة الإرسال والطباعة.
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BDProposal(models.Model):
    _name = "bd.proposal"
    _description = "Business Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        string="Name",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("proposal.sequence"),
        tracking=True,
    )
    client_name = fields.Char(string="Client Name", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Related Client", index=True, tracking=True
    )
    lead_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        index=True,
        tracking=True,
    )
    date = fields.Date(
        string="Proposal Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    reference = fields.Char(string="Reference", tracking=True)
    scope_of_work = fields.Html(string="Scope of Work", sanitize=False)
    legal_fees = fields.Float(string="Legal Fees", tracking=True)
    terms_conditions = fields.Html(string="Terms & Conditions", sanitize=False)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("rejected_closed", "Rejected & Closed"),
            ("client_approved", "Client Approved"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    collected_amount = fields.Float(string="Collected Amount", tracking=True)
    remaining_amount = fields.Float(
        string="Remaining Amount", compute="_compute_remaining_amount", store=True
    )
    comments = fields.Text(string="Comments / Rejection Reason")
    # ------------------------------------------------------------------------------
    # رابط الاتفاقية الناتجة عن العرض للاحتفاظ بعلاقة مباشرة بعد موافقة العميل.
    # ------------------------------------------------------------------------------
    engagement_letter_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        readonly=True,
        copy=False,
    )
    # ------------------------------------------------------------------------------
    # الحقول المالية: المحامي، تكلفة الساعة، ساعات التنفيذ، التكاليف الإضافية ونطاق المشروع.
    # ------------------------------------------------------------------------------
    lawyer_id = fields.Many2one("hr.employee", string="Assigned Lawyer", tracking=True)
    hourly_cost = fields.Float(string="Cost Per Hour", tracking=True, readonly=True)
    planned_hours = fields.Float(string="Planned Hours", tracking=True)
    additional_cost = fields.Float(string="Additional Cost", tracking=True)
    total_estimated_cost = fields.Float(string="Total Estimated Cost", compute="_compute_total_cost", store=True)
    services_description = fields.Text(string="Services Description")
    project_scope = fields.Text(string="Project Scope")
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        index=True,
    )

    # ------------------------------------------------------------------------------
    # دالة تحسب المبلغ المتبقي ديناميكياً بناءً على المدفوعات ورسوم العرض.
    # ------------------------------------------------------------------------------
    @api.depends("legal_fees", "collected_amount")
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = max(record.legal_fees - record.collected_amount, 0.0)

    # ------------------------------------------------------------------------------
    # دالة تحسب التكلفة الكلية المقدرة: (تكلفة الساعة × الساعات) + التكاليف الإضافية.
    # ------------------------------------------------------------------------------
    @api.depends("hourly_cost", "planned_hours", "additional_cost")
    def _compute_total_cost(self):
        for record in self:
            base = (record.hourly_cost or 0.0) * (record.planned_hours or 0.0)
            record.total_estimated_cost = base + (record.additional_cost or 0.0)

    # ------------------------------------------------------------------------------
    # عند اختيار المحامي يتم جلب تكلفة الساعة من cost.calculation تلقائياً.
    # ------------------------------------------------------------------------------
    @api.onchange("lead_id")
    def _onchange_lead_id(self):
        for record in self:
            if not record.lead_id:
                continue
            lead_client = record._prepare_lead_defaults(record.lead_id)
            if lead_client.get("partner_id"):
                record.partner_id = lead_client["partner_id"]
            if lead_client.get("client_name"):
                record.client_name = lead_client["client_name"]

    @api.onchange("lawyer_id")
    def _onchange_lawyer_id(self):
        for record in self:
            if not record.lawyer_id:
                continue
            cost = self.env["cost.calculation"].search([("employee_id", "=", record.lawyer_id.id)], limit=1)
            if cost:
                record.hourly_cost = cost.cost_per_hour
            else:
                record.hourly_cost = 0.0
    # ------------------------------------------------------------------------------
    # دالة مساعدة لضمان الانتقال الصحيح بين المراحل ومنع الازدواجية.
    # ------------------------------------------------------------------------------
    def _ensure_state(self, allowed_states):
        for proposal in self:
            if proposal.state not in allowed_states:
                raise UserError(
                    _("This action is only allowed from states: %s. Current state: %s")
                    % (", ".join(allowed_states), proposal.state)
                )

    # ------------------------------------------------------------------------------
    # عند الضغط على زر الإرسال للموافقة يتم تحويل الحالة إلى waiting_approval
    # مع إرسال Notification للمراجع.
    # ------------------------------------------------------------------------------
    def action_send_for_approval(self):
        self._ensure_state({"draft", "rejected"})
        for proposal in self:
            proposal.state = "waiting_approval"
            proposal.message_post(
                body=_("Proposal sent for approval to %s") % (proposal.reviewer_id.display_name or _("Reviewer"))
            )
            if proposal.reviewer_id:
                proposal.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=proposal.reviewer_id.id,
                    summary=_("Please review proposal %s") % proposal.name,
                )

    # ------------------------------------------------------------------------------
    # عند الموافقة:
    # - تتغير الحالة إلى approved
    # - يتم تفعيل زر الطباعة فقط بعد الموافقة
    # ------------------------------------------------------------------------------
    def action_approve(self):
        self._ensure_state({"waiting_approval"})
        for proposal in self:
            proposal.state = "approved"
            proposal.message_post(body=_("Proposal approved. Printing is now enabled."))

    @api.model_create_multi
    def create(self, vals_list):
        seq_model = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") in (_("New"), False):
                vals["name"] = seq_model.next_by_code("proposal.sequence")
            if vals.get("lawyer_id"):
                vals["hourly_cost"] = self._get_lawyer_cost(vals["lawyer_id"])
            lead_vals = vals.get("lead_id") and self._prepare_lead_defaults(vals["lead_id"]) or {}
            if lead_vals:
                vals.setdefault("client_name", lead_vals.get("client_name"))
                if lead_vals.get("partner_id") and not vals.get("partner_id"):
                    vals["partner_id"] = lead_vals["partner_id"]
        records = super().create(vals_list)
        return records

    def write(self, vals):
        if "lawyer_id" in vals and vals["lawyer_id"]:
            vals["hourly_cost"] = self._get_lawyer_cost(vals["lawyer_id"])
        if vals.get("lead_id"):
            lead_vals = self._prepare_lead_defaults(vals["lead_id"])
            if lead_vals:
                vals.setdefault("client_name", lead_vals.get("client_name"))
                if lead_vals.get("partner_id") and not vals.get("partner_id"):
                    vals["partner_id"] = lead_vals["partner_id"]
        return super().write(vals)

    def _get_lawyer_cost(self, lawyer_id):
        cost = self.env["cost.calculation"].search([("employee_id", "=", lawyer_id)], limit=1)
        return cost.cost_per_hour if cost else 0.0

    def _prepare_lead_defaults(self, lead):
        lead_record = lead if isinstance(lead, models.BaseModel) else self.env["crm.lead"].browse(lead)
        lead_record = lead_record if lead_record.exists() else False
        if not lead_record:
            return {}
        client_name = (
            lead_record.partner_id.display_name
            or lead_record.partner_name
            or lead_record.contact_name
            or lead_record.name
        )
        return {
            "client_name": client_name,
            "partner_id": lead_record.partner_id.id,
        }

    # ------------------------------------------------------------------------------
    # عند الرفض:
    # - الحالة إلى rejected
    # - يتم حفظ سبب الرفض في حقل comments
    # ------------------------------------------------------------------------------
    def action_reject(self):
        self._ensure_state({"waiting_approval"})
        for proposal in self:
            if not proposal.comments:
                raise UserError(_("Please provide the rejection comments before rejecting."))
            proposal.state = "rejected"
            proposal.message_post(body=_("Proposal rejected: %s") % proposal.comments)

    # ------------------------------------------------------------------------------
    # زر لتحديث حالة العرض عندما تتم الموافقة من العميل النهائي.
    # ------------------------------------------------------------------------------
    def action_client_approved(self):
        self._ensure_state({"approved"})
        for proposal in self:
            proposal.state = "client_approved"
            proposal.message_post(body=_("Client confirmed the proposal."))

    # ------------------------------------------------------------------------------
    # زر لإغلاق العرض نهائياً في حال رفضه وإغلاق الملف.
    # ------------------------------------------------------------------------------
    def action_close_rejected(self):
        self._ensure_state({"rejected"})
        for proposal in self:
            proposal.state = "rejected_closed"
            proposal.message_post(body=_("Rejected proposal has been closed."))

    # ------------------------------------------------------------------------------
    # زر يعيد العرض إلى المسودة إذا أراد المستخدم تحرير البيانات مرة أخرى.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        self._ensure_state({"rejected", "rejected_closed"})
        for proposal in self:
            proposal.state = "draft"

    # ------------------------------------------------------------------------------
    # زر الطباعة يقوم باستدعاء الـ QWeb report بعد التأكد من حالة الموافقة.
    # ------------------------------------------------------------------------------
    def action_print_proposal(self):
        for proposal in self:
            if proposal.state not in {"approved", "client_approved"}:
                raise UserError(_("Printing is available only after approval."))
        return self.env.ref("qlk_management.report_bd_proposal").report_action(self)

    # ------------------------------------------------------------------------------
    # بعد موافقة العميل يتم إنشاء اتفاقية وربطها بالعرض أو فتح القائمة الحالية.
    # ------------------------------------------------------------------------------
    def action_create_engagement_letter(self):
        self.ensure_one()
        if self.state != "client_approved":
            raise UserError(_("You can only create an engagement letter once the client approves the proposal."))

        letter = self.engagement_letter_id
        if not letter:
            if not self.partner_id:
                raise UserError(_("Please link the proposal to a customer before creating the engagement letter."))
            letter_vals = {
                "name": self.name or _("Engagement Letter"),
                "partner_id": self.partner_id.id,
                "date": fields.Date.context_today(self),
                "contract_type": "retainer",
                "retainer_type": "corporate",
                "comments": self.comments,
                "proposal_id": self.id,
                "lawyer_id": self.lawyer_id.id,
                "hourly_cost": self.hourly_cost,
                "planned_hours": self.planned_hours,
                "additional_cost": self.additional_cost,
                "total_estimated_cost": self.total_estimated_cost,
            }
            letter = self.env["bd.engagement.letter"].create(letter_vals)
            self.engagement_letter_id = letter.id
        elif not letter.proposal_id:
            letter.proposal_id = self.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "bd.engagement.letter",
            "res_id": letter.id,
            "view_mode": "form",
            "target": "current",
        }
