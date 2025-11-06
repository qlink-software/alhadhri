# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EngagementProposal(models.Model):
    _name = "qlk.engagement.proposal"
    _description = "Engagement Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("converted", "Converted"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_SELECTION = [
        ("paid", "Paid"),
        ("pro_bono", "Pro Bono"),
    ]

    DEPARTMENT_SELECTION = [
        ("C", "Corporate"),
        ("L", "Litigation"),
        ("CL", "Combined Litigation & Corporate"),
        ("A", "Arbitration"),
    ]

    name = fields.Char(string="Proposal Reference", copy=False, readonly=True, tracking=True, default="New")
    reference = fields.Char(string="Internal Reference", copy=False, readonly=True, tracking=True)
    state = fields.Selection(selection=STATE_SELECTION, default="draft", tracking=True, required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        required=True,
        tracking=True,
        domain="[('parent_id', '=', False)]",
    )
    department_type = fields.Selection(
        selection=DEPARTMENT_SELECTION,
        default="C",
        required=True,
        tracking=True,
    )
    payment_type = fields.Selection(
        selection=PAYMENT_SELECTION,
        string="Payment Type",
        default="paid",
        required=True,
        tracking=True,
    )
    service_description = fields.Html(string="Services Description", sanitize=False)
    estimated_hours = fields.Float(string="Estimated Hours", tracking=True)
    hourly_rate = fields.Monetary(string="Hourly Rate", tracking=True)
    additional_cost = fields.Monetary(string="Additional Costs", tracking=True)
    total_amount = fields.Monetary(
        string="Estimated Total Amount",
        compute="_compute_total_amount",
        store=True,
        readonly=False,
        help="Calculated value based on estimated hours, hourly rate, and additional costs.",
    )
    notes = fields.Text(string="Internal Notes")

    engagement_letter_id = fields.Many2one(
        "qlk.engagement.letter",
        string="Converted Engagement Letter",
        readonly=True,
        copy=False,
    )
    conversion_date = fields.Datetime(string="Conversion Date", readonly=True)
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True)
    approved_on = fields.Datetime(string="Approved On", readonly=True)

    def _ensure_can_modify(self):
        for record in self:
            if record.state not in ("draft", "approved"):
                raise ValidationError(_("Only draft or approved proposals can be modified."))

    @api.depends("estimated_hours", "hourly_rate", "additional_cost")
    def _compute_total_amount(self):
        for record in self:
            hours_total = (record.estimated_hours or 0.0) * (record.hourly_rate or 0.0)
            record.total_amount = hours_total + (record.additional_cost or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("state", "draft")
            if not vals.get("reference"):
                vals["reference"] = sequence.next_by_code("qlk.engagement.proposal") or _("New Proposal")
                vals["name"] = vals["reference"]
        return super().create(vals_list)

    def write(self, vals):
        if any(field in vals for field in ["partner_id", "department_type", "service_description", "estimated_hours", "hourly_rate", "additional_cost"]):
            self._ensure_can_modify()
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "cancelled"):
                raise ValidationError(_("Only draft or cancelled proposals can be deleted."))
        return super().unlink()

    def action_set_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise ValidationError(_("Only cancelled proposals can be reset to draft."))
            record.state = "draft"
        return True

    def action_approve_proposal(self):
        for record in self:
            if record.state == "converted":
                raise ValidationError(_("Converted proposals cannot be approved."))
            if record.state == "approved":
                continue
            record.state = "approved"
            record.approved_by_id = self.env.user
            record.approved_on = fields.Datetime.now()
        return True

    def action_cancel_proposal(self):
        for record in self:
            if record.state == "converted":
                raise ValidationError(_("Converted proposals cannot be cancelled."))
            record.state = "cancelled"
        return True

    def _prepare_engagement_letter_vals(self):
        self.ensure_one()
        contract_type = "lump_sum" if self.payment_type == "paid" else "retainer"
        return {
            "partner_id": self.partner_id.id,
            "department_type": self.department_type,
            "scope_of_work": self.service_description,
            "total_fees": self.total_amount if self.payment_type == "paid" else 0.0,
            "payment_type": self.payment_type,
            "estimated_hours": self.estimated_hours,
            "hourly_rate": self.hourly_rate,
            "additional_cost": self.additional_cost,
            "legacy_proposal_id": self.id,
            "contract_type": contract_type,
        }

    def action_convert_to_engagement(self):
        self.ensure_one()
        EngagementLetter = self.env["qlk.engagement.letter"]
        for record in self:
            if record.state == "converted":
                raise ValidationError(_("This proposal has already been converted into an engagement letter."))
            if not record.partner_id:
                raise ValidationError(_("Please set a client before converting the proposal."))
            vals = record._prepare_engagement_letter_vals()
            letter = EngagementLetter.create(vals)
            record.engagement_letter_id = letter.id
            record.state = "converted"
            record.conversion_date = fields.Datetime.now()
        return {
            "type": "ir.actions.act_window",
            "name": _("Engagement Letter"),
            "res_model": "qlk.engagement.letter",
            "view_mode": "form",
            "res_id": self.engagement_letter_id.id,
        }
    def action_open_engagement_letter(self):
        self.ensure_one()
        if not self.engagement_letter_id:
            raise ValidationError(_('This proposal has not been converted into an engagement letter yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Engagement Letter'),
            'res_model': 'qlk.engagement.letter',
            'view_mode': 'form',
            'res_id': self.engagement_letter_id.id,
        }
