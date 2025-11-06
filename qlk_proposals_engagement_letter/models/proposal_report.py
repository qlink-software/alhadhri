# -*- coding: utf-8 -*-
from odoo import fields, models

from .business_proposal import BusinessProposal


class ProposalReport(models.Model):
    _name = "qlk.proposal.report"
    _description = "Business Proposal Reporting"
    _auto = False
    _rec_name = "proposal_id"
    _order = "date desc, id desc"

    proposal_id = fields.Many2one(
        "qlk.business.proposal",
        string="Proposal",
        readonly=True,
    )
    date = fields.Date(readonly=True)
    status = fields.Selection(
        selection=BusinessProposal.STATUS_SELECTION,
        readonly=True,
    )
    report_status = fields.Selection(
        selection=BusinessProposal.REPORT_STATUS_SELECTION,
        readonly=True,
    )
    legal_fees = fields.Monetary(currency_field="currency_id", readonly=True)
    amount_collected = fields.Monetary(currency_field="currency_id", readonly=True)
    remaining_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    year = fields.Integer(readonly=True)
    month = fields.Integer(readonly=True)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS qlk_proposal_report")
        self.env.cr.execute(
            """
            CREATE VIEW qlk_proposal_report AS
            SELECT
                bp.id AS id,
                bp.id AS proposal_id,
                bp.company_id AS company_id,
                bp.currency_id AS currency_id,
                bp.date AS date,
                bp.status AS status,
                bp.report_status AS report_status,
                bp.legal_fees AS legal_fees,
                bp.amount_collected AS amount_collected,
                (COALESCE(bp.legal_fees, 0.0) - COALESCE(bp.amount_collected, 0.0)) AS remaining_amount,
                EXTRACT(YEAR FROM bp.date)::INTEGER AS year,
                EXTRACT(MONTH FROM bp.date)::INTEGER AS month
            FROM qlk_business_proposal bp
            WHERE bp.active = TRUE
            """
        )
