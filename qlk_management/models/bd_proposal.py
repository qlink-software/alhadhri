# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديل العروض (Business Proposal)
# يقوم هذا الموديل بإدارة دورة حياة العرض من الإنشاء وحتى موافقة العميل.
# يغطي إنشاء العرض، إرسال الموافقة، الرفض مع الأسباب، وإعادة الإرسال والطباعة.
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PAYMENT_STATUS_SELECTION = [
    ("unpaid", "Unpaid"),
    ("partial", "Partially Paid"),
    ("paid", "Paid"),
]

class BDProposal(models.Model):
    _name = "bd.proposal"
    _description = "Business Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin", "qlk.notification.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        string="Document Number",
        required=True,
        copy=False,
        default="/",
        tracking=True,
        readonly=True,
    )
    code = fields.Char(string="Proposal Code", default="/", copy=False, readonly=True)
    proposal_type = fields.Selection(
        selection=[("proposal", "Proposal"), ("el", "Engagement Letter")],
        string="Document Type",
        default="proposal",
        required=True,
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
    client_code = fields.Char(string="Client Code", copy=False, readonly=True)
    client_sequence = fields.Integer(string="Client Sequence", copy=False, readonly=True)
    partner_id = fields.Many2one(
        "res.partner", string="Related Client", index=True, tracking=True
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
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        compute="_compute_client_id",
        inverse="_inverse_client_id",
        store=True,
        index=True,
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
    billing_type = fields.Selection(
        [("free", "Pro bono"), ("billable", "Paid")],
        string="Billing Type",
        default="billable",
        tracking=True,
    )
    legal_fees = fields.Float(string="Legal Fees", tracking=True)
    legal_fees_lines = fields.One2many(
        "bd.proposal.legal.fee",
        "proposal_id",
        string="Legal Fees Lines",
    )
    scope_of_work = fields.Text(string="Scope of Work")
    payment_terms = fields.Char(string="Payment Terms")
    terms_conditions = fields.Html(string="Terms & Conditions", sanitize=False)
    state = fields.Selection(
        selection=[
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

    
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True,
    )
    
    rejection_reason = fields.Text(string="Rejection Reason")
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
    lawyer_id = fields.Many2one("res.partner", string="Assigned Lawyer", tracking=True)
    lawyer_ids = fields.Many2many(
        "hr.employee",
        "bd_proposal_lawyer_rel",
        "proposal_id",
        "employee_id",
        string="Assigned Lawyers",
        tracking=True,
    )
    lawyer_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Lawyer",
        compute="_compute_lawyer_employee_id",
        inverse="_inverse_lawyer_employee_id",
        store=True,
        tracking=True,
    )
    lawyer_cost_hour = fields.Float(string="Lawyer Cost Per Hour", readonly=True)
    hourly_cost = fields.Float(string="Cost Per Hour", tracking=True, readonly=True)
    planned_hours = fields.Float(string="Planned Hours", tracking=True)
    total_estimated_cost = fields.Float(string="Total Estimated Cost", compute="_compute_total_cost", store=True)
    services_description = fields.Text(string="Services Description")
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
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
    time_entry_ids = fields.One2many(
        "qlk.task",
        "proposal_id",
        string="Hours / Time Entries",
    )
    hours_logged_ok = fields.Boolean(
        string="Hours Logged?",
        compute="_compute_hours_logged_ok",
        store=True,
        default=False,
        help="Automatically toggled based on logging tasks/hours",
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
            if record.partner_id == record.client_id:
                continue
            record.with_context(skip_client_partner_sync=True).write(
                {"partner_id": record.client_id.id}
            )

    # ------------------------------------------------------------------------------
    # دالة تحسب المبلغ المتبقي ديناميكياً بناءً على المدفوعات ورسوم العرض.
    # ------------------------------------------------------------------------------
    @api.depends("legal_fees_lines.amount", "legal_fees", "billing_type")
    def _compute_total_amount(self):
        for record in self:
            if record.billing_type == "free":
                record.total_amount = 0.0
                continue
            lines_total = sum(record.legal_fees_lines.mapped("amount"))
            if lines_total:
                record.total_amount = lines_total
            else:
                record.total_amount = record.legal_fees or 0.0



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

    # ------------------------------------------------------------------------------
    # دالة تحسب التكلفة الكلية المقدرة: (تكلفة الساعة × الساعات) + التكاليف الإضافية.
    # ------------------------------------------------------------------------------
    @api.depends("hourly_cost", "planned_hours")
    def _compute_total_cost(self):
        for record in self:
            base = (record.hourly_cost or 0.0) * (record.planned_hours or 0.0)
            record.total_estimated_cost = base

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

    @api.depends("lead_id")
    @api.onchange("client_id")
    def _onchange_client_id(self):
        for record in self:
            if record.client_id:
                record.partner_id = record.client_id

    @api.onchange("lawyer_id")
    def _onchange_lawyer_id(self):
        for record in self:
            if not record.lawyer_id:
                continue
            cost, found = record._find_lawyer_cost(record.lawyer_id.id)
            if found:
                record.lawyer_cost_hour = cost
                record.hourly_cost = cost
            else:
                record.lawyer_cost_hour = 0.0
                record.hourly_cost = 0.0
                raise UserError(_("Cost calculation missing for this lawyer!"))

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
    # إرسال العرض إلى موافقة المدير (Draft -> Waiting Manager Approval).
    # ------------------------------------------------------------------------------
    def action_send_manager_approval(self):
        self._ensure_state({"draft"})
        for proposal in self:
            proposal.write(
                {
                    "rejection_reason": False,
                    "state": "waiting_manager_approval",
                }
            )
            proposal.message_post(body=_("Proposal submitted for manager approval."))

    # ------------------------------------------------------------------------------
    # موافقة المدير (Waiting Manager Approval -> Approved by Manager).
    # ------------------------------------------------------------------------------
    def action_manager_approve(self):
        self._ensure_state({"waiting_manager_approval"})
        for proposal in self:
            proposal._check_approval_rights()
            proposal.write(
                {
                    "approved_by": self.env.user.id,
                    "state": "approved_manager",
                }
            )
            proposal.message_post(body=_("Manager approved. Ready to send to client."))

    # ------------------------------------------------------------------------------
    # إرسال العرض لموافقة العميل (Approved by Manager -> Waiting Client Approval).
    # ------------------------------------------------------------------------------
    def action_send_client_approval(self):
        self._ensure_state({"approved_manager"})
        for proposal in self:
            proposal._check_approval_rights()
            proposal.write({"state": "waiting_client_approval"})
            proposal.message_post(body=_("Proposal sent for client approval."))

    def action_send_for_approval(self):
        return self.action_send_manager_approval()

    def action_approve(self):
        return self.action_manager_approve()

    @api.model_create_multi
    def create(self, vals_list):
        sequence_cache = {}
        for vals in vals_list:
            if vals.get("partner_id") and not vals.get("client_id"):
                vals["client_id"] = vals["partner_id"]
            if vals.get("lawyer_id"):
                lawyer_cost = self._get_lawyer_cost(vals["lawyer_id"])
                vals["hourly_cost"] = lawyer_cost
                vals["lawyer_cost_hour"] = lawyer_cost
            if vals.get("client_id") and not vals.get("partner_id"):
                vals["partner_id"] = vals["client_id"]
            lead_vals = vals.get("lead_id") and self._prepare_lead_defaults(vals["lead_id"]) or {}
            if lead_vals and lead_vals.get("partner_id") and not vals.get("partner_id"):
                vals["partner_id"] = lead_vals["partner_id"]
            self._prepare_partner_sequence_vals(vals, sequence_cache)
        records = super().create(vals_list)
        records._copy_partner_attachments()
        for proposal in records:
            if proposal.lead_id:
                tasks = self.env["qlk.task"].search([("lead_id", "=", proposal.lead_id.id)])
                if tasks:
                    tasks.write({"lead_id": False, "proposal_id": proposal.id})
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # records._check_hours_logged()
        return records

    def write(self, vals):
        vals = dict(vals)
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # if self._has_new_task_command(vals.get("time_entry_ids")):
        #     return super().write(vals)
        # if self._requires_new_task_on_write(vals):
        #     self._raise_missing_hours_error()
        restricted = {"name", "client_code", "client_sequence", "code"}
        if restricted.intersection(vals) and not self.env.context.get("allow_document_number_update"):
            raise UserError(_("Document numbers and client codes cannot be modified manually."))
        if not self.env.context.get("skip_client_partner_sync"):
            if vals.get("partner_id") and not vals.get("client_id"):
                vals["client_id"] = vals["partner_id"]
            if vals.get("client_id") and not vals.get("partner_id"):
                vals["partner_id"] = vals["client_id"]
        if any(
            field in vals
            for field in (
                "legal_fees_lines",
                "legal_fees",
                "currency_id",
                "billing_type",
            )
        ):
            for proposal in self:
                if proposal.state in {"approved_manager", "waiting_client_approval", "approved_client"}:
                    raise UserError(_("Financial fields are locked after approval."))
        if "lawyer_id" in vals and vals["lawyer_id"]:
            lawyer_cost = self._get_lawyer_cost(vals["lawyer_id"])
            vals["hourly_cost"] = lawyer_cost
            vals["lawyer_cost_hour"] = lawyer_cost
        if vals.get("lead_id"):
            lead_vals = self._prepare_lead_defaults(vals["lead_id"])
        res = super().write(vals)
        if any(field in vals for field in ("legal_fees", "billing_type")):
            self.mapped("engagement_letter_id")._sync_proposal_financials()
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
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
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # Task = self.env["qlk.task"]
        # for record in self:
        #     if not Task.search_count([("proposal_id", "=", record.id)]):
        #         record._raise_missing_hours_error()
        return True

    def _requires_new_task_on_write(self, vals):
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

    def _prepare_partner_sequence_vals(self, vals, sequence_cache):
        partner_id = vals.get("partner_id")
        if not partner_id:
            raise UserError(_("Please select a client before creating the document."))
        partner = self.env["res.partner"].browse(partner_id)
        client_code = partner._get_client_code()
        proposal_type = vals.get("proposal_type") or "proposal"
        seq_number = self._next_client_sequence(partner.id, proposal_type, sequence_cache)
        vals["proposal_type"] = proposal_type
        vals["client_code"] = client_code
        vals["client_sequence"] = seq_number
        document_number = self._build_document_number(client_code, proposal_type, seq_number)
        vals["name"] = document_number
        vals["code"] = document_number

    def _next_client_sequence(self, partner_id, proposal_type, sequence_cache):
        cache_key = (partner_id, proposal_type)
        last_number = sequence_cache.get(cache_key)
        if last_number is None:
            domain = [("partner_id", "=", partner_id), ("proposal_type", "=", proposal_type)]
            last = self.search(domain, order="client_sequence desc", limit=1)
            last_number = last.client_sequence if last else 0
        sequence_cache[cache_key] = (last_number or 0) + 1
        return sequence_cache[cache_key]

    def _build_document_number(self, client_code, proposal_type, seq_number):
        seq_text = f"{seq_number:03d}"
        if proposal_type == "proposal":
            return f"{client_code}/PROP{seq_text}"
        return f"{client_code}/EL{seq_text}"

    def _sync_client_code_from_partner(self):
        for proposal in self:
            if not proposal.partner_id:
                continue
            client_code = proposal.partner_id._get_client_code()
            if not proposal.client_sequence:
                continue
            doc_number = proposal._build_document_number(
                client_code, proposal.proposal_type, proposal.client_sequence
            )
            proposal.with_context(
                allow_document_number_update=True,
                skip_client_partner_sync=True,
            ).write({"client_code": client_code, "name": doc_number, "code": doc_number})

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
        for proposal in self:
            partner = proposal.partner_id
            if not partner:
                continue
            for attachment in attachments_by_partner.get(partner.id, []):
                attachment.copy(
                    {
                        "res_model": proposal._name,
                        "res_id": proposal.id,
                    }
                )

    def _prepare_lead_defaults(self, lead):
        lead_record = lead if isinstance(lead, models.BaseModel) else self.env["crm.lead"].browse(lead)
        lead_record = lead_record if lead_record.exists() else False
        if not lead_record:
            return {}
        return {
            "partner_id": lead_record.partner_id.id,
        }

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
        for proposal in self:
            proposal._check_approval_rights()
        return self._open_rejection_wizard("manager")

    # ------------------------------------------------------------------------------
    # رفض العميل (Waiting Client Approval -> Rejected).
    # ------------------------------------------------------------------------------
    def action_client_reject(self):
        self.ensure_one()
        self._ensure_state({"waiting_client_approval"})
        for proposal in self:
            proposal._check_approval_rights()
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
        for proposal in self:
            proposal._check_approval_rights()
            proposal.write(
                {
                    "rejection_reason": reason,
                    "state": "rejected",
                }
            )
            proposal.message_post(body=_("Proposal rejected: %s") % reason)

    # ------------------------------------------------------------------------------
    # زر لتحديث حالة العرض عندما تتم الموافقة من العميل النهائي.
    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    # موافقة العميل (Waiting Client Approval -> Approved by Client).
    # ------------------------------------------------------------------------------
    def action_client_approve(self):
        self._ensure_state({"waiting_client_approval"})
        for proposal in self:
            proposal._check_approval_rights()
            proposal.write(
                {
                    "approved_by": self.env.user.id,
                    "state": "approved_client",
                }
            )
            proposal.message_post(body=_("Client approved the proposal."))

    def action_client_approved(self):
        return self.action_client_approve()

    # ------------------------------------------------------------------------------
    # زر لإغلاق العرض نهائياً في حال رفضه وإغلاق الملف.
    # ------------------------------------------------------------------------------
    def action_close_rejected(self):
        self._ensure_state({"rejected"})
        for proposal in self:
            proposal.write({"state": "cancelled"})
            proposal.message_post(body=_("Rejected proposal has been cancelled."))

    # ------------------------------------------------------------------------------
    # زر يعيد العرض إلى المسودة إذا أراد المستخدم تحرير البيانات مرة أخرى.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        self._ensure_state({"rejected", "cancelled"})
        for proposal in self:
            proposal.write(
                {
                    "rejection_reason": False,
                    "state": "draft",
                }
            )

    # ------------------------------------------------------------------------------
    # زر الطباعة يقوم باستدعاء الـ QWeb report بعد التأكد من حالة الموافقة.
    # ------------------------------------------------------------------------------
    def action_print_proposal(self):
        for proposal in self:
            if proposal.state != "approved_client":
                raise UserError(_("Printing is available only after approval."))
        return self.env.ref("qlk_management.report_bd_proposal").report_action(self)

    # ------------------------------------------------------------------------------
    # بعد موافقة العميل يتم إنشاء اتفاقية وربطها بالعرض أو فتح القائمة الحالية.
    # ------------------------------------------------------------------------------
    def action_create_engagement_letter(self):
        self.ensure_one()
        if self.state != "approved_client":
            raise UserError(_("You can only create an engagement letter once the proposal is approved by the client."))

        letter = self.engagement_letter_id
        if not letter:
            if not self.partner_id:
                raise UserError(_("Please link the proposal to a customer before creating the engagement letter."))
            letter_vals = self._prepare_engagement_letter_vals()
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

    def _prepare_engagement_letter_vals(self):
        self.ensure_one()
        partner = self.partner_id
        partner_code = partner._get_client_code()
        fee_lines = [
            (0, 0, {"description": line.description, "amount": line.amount, "due_date": line.due_date})
            for line in self.legal_fees_lines
        ]
        primary_employee = self.lawyer_employee_id
        if not primary_employee and self.lawyer_ids:
            primary_employee = self.lawyer_ids[:1]
        primary_partner = self._partner_from_employee(primary_employee) if primary_employee else self.env["res.partner"]
        return {
            "partner_id": partner.id,
            "client_id": partner.id,
            "client_code": partner_code,
            "date": fields.Date.context_today(self),
            "contract_type": "retainer",
            "legal_fee_amount": self.legal_fees,
            "total_amount": self.total_amount,
            "currency_id": self.currency_id.id,
            "payment_terms": self.payment_terms,
            "comments": self.comments,
            "proposal_id": self.id,
            "legal_fees_lines": fee_lines,
            "scope_of_work": self.scope_of_work,
            "approval_role": self.approval_role,
            "lawyer_id": primary_partner.id if primary_partner else False,
            "lawyer_employee_id": primary_employee.id if primary_employee else False,
            "lawyer_ids": [(6, 0, self.lawyer_ids.ids)] if self.lawyer_ids else False,
            "hourly_cost": self.hourly_cost,
            "lawyer_cost_hour": self.lawyer_cost_hour,
            "planned_hours": self.planned_hours,
            "estimated_hours": self.planned_hours,
            "total_estimated_cost": self.total_estimated_cost,
            "billing_type": self.billing_type,
            "retainer_type": self.retainer_type,
            "services_description": False,
            "description": self.comments or _("Legal engagement for client %s") % (partner.display_name,),
        }

    def action_view_client_attachments(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError(_("Please set a client before opening attachments."))
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
        for proposal in self:
            if proposal.approval_role == "manager" and not self.env.user.has_group(
                "qlk_management.bd_manager_group"
            ):
                raise UserError(_("Only Managers can approve or reject this document."))
            if proposal.approval_role == "assistant_manager" and not self.env.user.has_group(
                "qlk_management.bd_assistant_manager_group"
            ):
                raise UserError(_("Only Assistant Managers can approve or reject this document."))


class BDProposalLegalFee(models.Model):
    _name = "bd.proposal.legal.fee"
    _description = "BD Proposal Legal Fee Line"

    proposal_id = fields.Many2one(
        "bd.proposal",
        string="Proposal",
        required=True,
        ondelete="cascade",
        index=True,
    )
    description = fields.Char(string="Description", required=True)
    amount = fields.Monetary(string="Amount", required=True)
    due_date = fields.Date(string="Due Date")
    currency_id = fields.Many2one(
        related="proposal_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )
