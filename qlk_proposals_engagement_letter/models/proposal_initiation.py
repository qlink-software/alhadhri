# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProposalInitiation(models.Model):
    _name = "qlk.proposal.initiation"
    _description = "Proposal Initiation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Initiation Reference",
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
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
        compute="_compute_currency",
        inverse="_inverse_currency",
        store=True,
    )
    number_of_cases = fields.Integer(string="Number of Cases", tracking=True)
    scope_of_work = fields.Text(string="Scope of Work", tracking=True)
    pricing_table_id = fields.Many2one(
        "qlk.pricing.table",
        string="Pricing Table",
        tracking=True,
        required=False,
        domain="[('company_id', '=', company_id)]",
    )
    estimated_cost = fields.Monetary(
        string="Estimated Cost",
        currency_field="currency_id",
        compute="_compute_estimated_cost",
        store=True,
        tracking=True,
    )
    proposal_ids = fields.One2many(
        "qlk.business.proposal",
        "initiation_id",
        string="Business Proposals",
    )
    proposal_count = fields.Integer(
        string="Proposal Count",
        compute="_compute_proposal_count",
        store=False,
    )

    _sql_constraints = [
        ("number_of_cases_positive", "CHECK(number_of_cases >= 0)", "Number of cases must be zero or positive."),
    ]

    @api.depends("pricing_table_id.currency_id", "company_id.currency_id")
    def _compute_currency(self):
        for record in self:
            record.currency_id = record.pricing_table_id.currency_id or record.company_id.currency_id

    def _inverse_currency(self):
        """Allow manual override if needed."""
        for record in self:
            if not record.currency_id:
                record.currency_id = record.company_id.currency_id

    @api.depends("number_of_cases", "pricing_table_id", "pricing_table_id.avg_case_cost")
    def _compute_estimated_cost(self):
        for record in self:
            if record.pricing_table_id:
                record.estimated_cost = (record.number_of_cases or 0) * record.pricing_table_id.avg_case_cost
            else:
                record.estimated_cost = 0.0

    @api.depends("proposal_ids")
    def _compute_proposal_count(self):
        for record in self:
            record.proposal_count = len(record.proposal_ids)

    @api.constrains("number_of_cases")
    def _check_number_of_cases(self):
        for record in self:
            if record.number_of_cases < 0:
                raise ValidationError(_("Number of cases must be zero or positive."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env.ref("qlk_proposals_engagement_letter.seq_proposal_initiation", raise_if_not_found=False)
        for vals in vals_list:
            if sequence:
                vals.setdefault("name", sequence.next_by_id())
            else:
                vals.setdefault("name", self.env["ir.sequence"].next_by_code("qlk.proposal.initiation") or _("New Initiation"))
        return super().create(vals_list)

    def action_view_proposals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Business Proposals"),
            "res_model": "qlk.business.proposal",
            "view_mode": "list,form",
            "domain": [("initiation_id", "=", self.id)],
            "context": {"default_initiation_id": self.id},
        }

    def action_create_proposal(self):
        self.ensure_one()
        if not self.scope_of_work:
            raise ValidationError(_("Please provide the scope of work before creating a proposal."))
        values = {
            "initiation_id": self.id,
            "scope_of_work": self.scope_of_work,
            "estimated_cost": self.estimated_cost,
            "client_name": self.env.context.get("default_client_name") or _("Client"),
            "legal_fees": self.estimated_cost,
            "date": fields.Date.context_today(self),
        }
        proposal = self.env["qlk.business.proposal"].create(values)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Business Proposal"),
            "res_model": "qlk.business.proposal",
            "view_mode": "form",
            "res_id": proposal.id,
            "context": {"default_initiation_id": self.id},
        }
        return action
