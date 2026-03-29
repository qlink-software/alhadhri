from odoo import fields, models, _
from odoo.exceptions import UserError


class HrApplicantOfferRejectWizard(models.TransientModel):
    _name = "hr.applicant.offer.reject.wizard"
    _description = "Reject Job Offer Wizard"

    applicant_id = fields.Many2one("hr.applicant", required=True)
    reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason:
            raise UserError(_("Rejection reason is required."))
        self.applicant_id.action_mark_offer_rejected(self.reason)
        return {"type": "ir.actions.act_window_close"}
