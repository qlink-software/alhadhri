# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bd_proposal_template_id = fields.Many2one(
        "bd.pdf.builder.template",
        string="Default Proposal PDF Template",
        domain="[('model', '=', 'bd.proposal')]",
    )
    bd_engagement_template_id = fields.Many2one(
        "bd.pdf.builder.template",
        string="Default Engagement PDF Template",
        domain="[('model', '=', 'bd.engagement.letter')]",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bd_proposal_template_id = fields.Many2one(
        related="company_id.bd_proposal_template_id",
        readonly=False,
        domain="[('model', '=', 'bd.proposal')]",
    )
    bd_engagement_template_id = fields.Many2one(
        related="company_id.bd_engagement_template_id",
        readonly=False,
        domain="[('model', '=', 'bd.engagement.letter')]",
    )
