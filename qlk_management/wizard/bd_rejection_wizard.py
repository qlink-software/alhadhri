# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class BDRejectionWizard(models.TransientModel):
    _name = "bd.rejection.wizard"
    _description = "BD Rejection Wizard"

    rejection_role = fields.Selection(
        [("manager", "Manager"), ("client", "Client")],
        string="Rejection Role",
        required=True,
    )
    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if not active_model or not active_ids:
            raise UserError(_("No active document to reject."))
        records = self.env[active_model].browse(active_ids)
        if not hasattr(records, "_apply_rejection_reason"):
            raise UserError(_("Rejection is not supported for this document."))
        records._apply_rejection_reason(self.rejection_reason, self.rejection_role)
        return {"type": "ir.actions.act_window_close"}
