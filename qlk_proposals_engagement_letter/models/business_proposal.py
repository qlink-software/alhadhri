# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BusinessProposal(models.Model):
    _name = "qlk.business.proposal"
    _description = "Business Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    STATUS_SELECTION = [
        ("draft", "Draft"),
        ("waiting", "Waiting Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("converted", "Converted"),
        ("closed", "Closed"),
    ]

    REPORT_STATUS_SELECTION = [
        ("approved_client", "Approved by Client"),
        ("rejected_client", "Rejected by Client"),
    ]

    name = fields.Char(string="Proposal Reference", readonly=True, copy=False, default="New", tracking=True)
    initiation_id = fields.Many2one(
        "qlk.proposal.initiation",
        string="Initiation Record",
        tracking=True,
        ondelete="set null",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    client_name = fields.Char(string="Client Name", required=True, tracking=True)
    date = fields.Date(default=lambda self: fields.Date.context_today(self), required=True, tracking=True)
    reference_no = fields.Char(string="Reference Number", tracking=True)
    scope_of_work = fields.Text(string="Scope of Work", tracking=True)
    legal_fees = fields.Monetary(string="Legal Fees", currency_field="currency_id", tracking=True)
    terms_conditions = fields.Text(string="Terms and Conditions")
    estimated_cost = fields.Monetary(
        string="Estimated Cost",
        related="initiation_id.estimated_cost",
        store=True,
        readonly=True,
        currency_field="currency_id",
    )
    number_of_cases = fields.Integer(
        string="Number of Cases",
        related="initiation_id.number_of_cases",
        store=True,
        readonly=True,
    )
    status = fields.Selection(selection=STATUS_SELECTION, default="draft", tracking=True, required=True)
    reviewer_comment = fields.Text(string="Reviewer Comment", tracking=True)
    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True, tracking=True)
    approved_on = fields.Datetime(string="Approved On", readonly=True)
    amount_collected = fields.Monetary(
        string="Amount Collected",
        currency_field="currency_id",
        tracking=True,
        default=0.0,
    )
    active = fields.Boolean(default=True)
    remaining_amount = fields.Monetary(
        string="Remaining Amount",
        currency_field="currency_id",
        compute="_compute_remaining_amount",
        store=True,
    )
    report_status = fields.Selection(
        selection=REPORT_STATUS_SELECTION,
        string="Client Decision",
        tracking=True,
    )
    engagement_id = fields.Many2one(
        "qlk.engagement.letter",
        string="Engagement Letter",
        readonly=True,
        copy=False,
    )
    activity_user_id = fields.Many2one(
        "res.users",
        string="Assigned Reviewer",
        tracking=True,
    )
    proposal_pdf_printed = fields.Boolean(string="PDF Printed", default=False, readonly=True)
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
    cost_additional_amount = fields.Float(string="Additional Cost", default=0.0, tracking=True)
    cost_total_amount = fields.Float(
        string="Total Cost",
        compute="_compute_cost_amounts",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        ("legal_fees_positive", "CHECK(legal_fees >= 0)", "Legal fees must be zero or positive."),
    ]

    @api.depends("legal_fees", "amount_collected")
    def _compute_remaining_amount(self):
        for record in self:
            total = record.legal_fees or 0.0
            collected = record.amount_collected or 0.0
            record.remaining_amount = total - collected

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

    @api.onchange("initiation_id")
    def _onchange_initiation_id(self):
        for record in self:
            if record.initiation_id:
                if not record.scope_of_work:
                    record.scope_of_work = record.initiation_id.scope_of_work
                if not record.legal_fees:
                    record.legal_fees = record.initiation_id.estimated_cost
                if not record.client_name:
                    record.client_name = _("Client")

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env.ref("qlk_proposals_engagement_letter.seq_business_proposal", raise_if_not_found=False)
        for vals in vals_list:
            if sequence:
                vals.setdefault("name", sequence.next_by_id())
            else:
                vals.setdefault("name", self.env["ir.sequence"].next_by_code("qlk.business.proposal") or _("New Proposal"))
            if not vals.get("legal_fees"):
                initiation_id = vals.get("initiation_id")
                if initiation_id:
                    initiation = self.env["qlk.proposal.initiation"].browse(initiation_id)
                    vals["legal_fees"] = initiation.estimated_cost
            employee_id = vals.get("employee_id")
            if employee_id and not vals.get("cost_calculation_id"):
                cost_calc = self._get_cost_calculation_for_employee_id(employee_id)
                vals["cost_calculation_id"] = cost_calc.id if cost_calc else False
        records = super().create(vals_list)
        records._apply_cost_calculation()
        return records

    def write(self, vals):
        if self.env.context.get("skip_cost_sync"):
            return super().write(vals)
        status = vals.get("status")
        if status and status not in dict(self.STATUS_SELECTION):
            raise ValidationError(_("Invalid status transition."))
        result = super().write(vals)
        if "employee_id" in vals:
            self._apply_cost_calculation()
        return result

    def _ensure_can_transition(self, allowed_from_states):
        for record in self:
            if record.status not in allowed_from_states:
                raise ValidationError(
                    _("Operation not allowed while proposal is in %(status)s state.", status=record.status.title())
                )

    def _notify_group(self, group_xml_id, body):
        partners = self.env["res.partner"]
        try:
            partners |= self.env.ref(group_xml_id).users.mapped("partner_id")
        except ValueError:
            partners |= self.env.user.partner_id
        if partners:
            self.message_post(body=body, partner_ids=partners.ids, subtype_xmlid="mail.mt_comment")

    def action_send_for_approval(self):
        self._ensure_can_transition({"draft", "rejected"})
        for record in self:
            record.status = "waiting"
            record.activity_user_id = record.activity_user_id or self.env.user
            record._notify_group(
                "qlk_proposals_engagement_letter.group_legal_manager",
                _(
                    "Proposal %(name)s has been submitted for approval by %(user)s.",
                    name=record.name,
                    user=self.env.user.name,
                ),
            )
        return True

    def action_approve(self):
        self._ensure_can_transition({"waiting"})
        if not self.env.user.has_group("qlk_proposals_engagement_letter.group_legal_manager"):
            raise ValidationError(_("Only legal managers can approve proposals."))
        for record in self:
            record.status = "approved"
            record.approved_by = self.env.user
            record.approved_on = fields.Datetime.now()
            record._notify_group(
                "qlk_proposals_engagement_letter.group_legal_employee",
                _("Proposal %(name)s has been approved.", name=record.name),
            )
        return True

    def action_reject(self):
        self._ensure_can_transition({"waiting"})
        if not self.env.user.has_group("qlk_proposals_engagement_letter.group_legal_manager"):
            raise ValidationError(_("Only legal managers can reject proposals."))
        for record in self:
            if not (record.reviewer_comment or self.env.context.get("reviewer_comment")):
                raise ValidationError(_("Please add reviewer comments before rejecting the proposal."))
            record.status = "rejected"
            record._notify_group(
                "qlk_proposals_engagement_letter.group_legal_employee",
                _(
                    "Proposal %(name)s has been rejected with comment: %(comment)s",
                    name=record.name,
                    comment=record.reviewer_comment or _("No comment provided"),
                ),
            )
        return True

    def action_resubmit(self):
        self._ensure_can_transition({"rejected"})
        for record in self:
            record.reviewer_comment = False
            record.status = "waiting"
            record._notify_group(
                "qlk_proposals_engagement_letter.group_legal_manager",
                _("Proposal %(name)s has been resubmitted for approval.", name=record.name),
            )
        return True

    def action_print_pdf(self):
        for record in self:
            if record.status != "approved":
                raise ValidationError(_("You can only print a proposal that is approved."))
            record.proposal_pdf_printed = True
        return self.env.ref("qlk_proposals_engagement_letter.action_report_business_proposal").report_action(self)

    def action_convert_to_engagement(self):
        self.ensure_one()
        if self.status != "approved":
            raise ValidationError(_("Only approved proposals can be converted."))
        if self.report_status != "approved_client":
            raise ValidationError(_("Client must approve the proposal before conversion."))
        if self.engagement_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "qlk.engagement.letter",
                "view_mode": "form",
                "res_id": self.engagement_id.id,
            }
        letter_values = {
            "proposal_id": self.id,
            "scope_of_work": self.scope_of_work,
            "total_fees": self.legal_fees,
            "notes": self.terms_conditions,
            "contract_type": "lump_sum",
            "department_type": "C",
            "company_id": self.company_id.id,
            "employee_id": self.employee_id.id if self.employee_id else False,
            "cost_calculation_id": self.cost_calculation_id.id if self.cost_calculation_id else False,
            "cost_additional_amount": self.cost_additional_amount,
        }
        if self.client_name:
            letter_values.update(
                {
                    "client_type": "company",
                    "company_name": self.client_name,
                }
            )
        engagement = self.env["qlk.engagement.letter"].create(letter_values)
        self.write({"engagement_id": engagement.id, "status": "converted"})
        return {
            "type": "ir.actions.act_window",
            "name": _("Engagement Letter"),
            "res_model": "qlk.engagement.letter",
            "view_mode": "form",
            "res_id": engagement.id,
        }

    def action_close_proposal(self):
        if not self.env.user.has_group("qlk_proposals_engagement_letter.group_general_manager"):
            raise ValidationError(_("Only the general manager can close proposals."))
        for record in self:
            record.status = "closed"
            record._notify_group(
                "qlk_proposals_engagement_letter.group_general_manager",
                _("Proposal %(name)s has been closed by %(user)s.", name=record.name, user=self.env.user.name),
            )
        return True

    def action_reject_and_close(self):
        for record in self:
            record.status = "closed"
            record.report_status = "rejected_client"
            record._notify_group(
                "qlk_proposals_engagement_letter.group_general_manager",
                _("Proposal %(name)s has been rejected by the client and closed.", name=record.name),
            )
        return True
