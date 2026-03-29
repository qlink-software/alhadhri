# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class QlkHrResignationRejectWizard(models.TransientModel):
    _name = "qlk.hr.resignation.reject.wizard"
    _description = "Resignation Rejection Wizard"

    request_id = fields.Many2one(
        "hr.resignation.request",
        string="Resignation Request",
        required=True,
    )
    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        if self.request_id.approval_state != "submitted":
            raise UserError(_("Only submitted resignation requests can be rejected."))
        self.request_id.action_reject_with_reason(self.rejection_reason)
        return {"type": "ir.actions.act_window_close"}
