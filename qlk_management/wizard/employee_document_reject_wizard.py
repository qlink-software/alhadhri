# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class QLKEmployeeDocumentRejectWizard(models.TransientModel):
    _name = "qlk.employee.document.reject.wizard"
    _description = "Employee Document Rejection Wizard"

    document_id = fields.Many2one(
        "qlk.employee.document",
        required=True,
    )
    rejection_reason = fields.Text(required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        document = self.document_id
        if document.status != "waiting_approval":
            raise UserError(_("Only documents waiting for approval can be rejected."))
        document.sudo().with_context(allow_status_update=True).write(
            {
                "status": "rejected",
                "rejection_reason": self.rejection_reason,
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            }
        )
        return {"type": "ir.actions.act_window_close"}
