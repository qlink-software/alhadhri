# -*- coding: utf-8 -*-
"""Wizards for audited hour adjustment and agreement reload confirmation."""

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class QlkProjectHourAdjustmentWizard(models.TransientModel):
    """Collect the mandatory reason for a manual consumed-hour adjustment."""

    _name = "qlk.project.hour.adjustment.wizard"
    _description = "Adjust Project Consumed Hours"

    project_id = fields.Many2one("qlk.project", required=True, readonly=True)
    current_value = fields.Float(
        string="Old Value",
        related="project_id.consumed_hours",
        readonly=True,
    )
    new_value = fields.Float(string="New Value", required=True)
    reason = fields.Text(required=True)

    def action_apply(self):
        """Validate the reason and delegate the audited ledger adjustment."""
        self.ensure_one()
        if not (self.reason or "").strip():
            raise ValidationError(_("A reason is required for manual consumed-hour changes."))
        self.project_id._apply_manual_consumed_hours(self.new_value, self.reason)
        return {"type": "ir.actions.client", "tag": "reload"}


class QlkProjectAgreementReloadWizard(models.TransientModel):
    """Ask whether project information should be reloaded from an agreement."""

    _name = "qlk.project.agreement.reload.wizard"
    _description = "Reload Project Information from Agreement"

    project_id = fields.Many2one("qlk.project", required=True, readonly=True)
    agreement_id = fields.Many2one(
        "bd.engagement.letter",
        string="Agreement",
        required=True,
        domain="[('partner_id', '=', project_id.client_id), ('state', '=', 'approved_client')]",
    )

    def action_reload(self):
        """Change the agreement and reload all supported project information."""
        self.ensure_one()
        self.project_id._change_agreement(self.agreement_id, reload_information=True)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_keep(self):
        """Change only the agreement reference and preserve project values."""
        self.ensure_one()
        self.project_id._change_agreement(self.agreement_id, reload_information=False)
        return {"type": "ir.actions.client", "tag": "reload"}
