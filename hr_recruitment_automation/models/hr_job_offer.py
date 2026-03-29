from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    candidate_name = fields.Char(string="Candidate Name", compute="_compute_candidate_name", store=True)
    total_salary = fields.Monetary(
        string="Total Salary",
        currency_field="currency_id",
        compute="_compute_total_salary",
        store=True,
    )
    offer_date = fields.Date(string="Offer Date", copy=False, tracking=True)

    @api.depends("recruitment_full_name", "partner_name")
    def _compute_candidate_name(self):
        for applicant in self:
            applicant.candidate_name = applicant.recruitment_full_name or applicant.partner_name or False

    @api.depends(
        "basic_salary",
        "housing_allowance",
        "transportation_allowance",
        "phone_allowance",
        "other_allowance",
    )
    def _compute_total_salary(self):
        for applicant in self:
            applicant.total_salary = (
                (applicant.basic_salary or 0.0)
                + (applicant.housing_allowance or 0.0)
                + (applicant.transportation_allowance or 0.0)
                + (applicant.phone_allowance or 0.0)
                + (applicant.other_allowance or 0.0)
            )

    def _ensure_offer_date(self):
        today = fields.Date.context_today(self)
        for applicant in self.filtered(lambda rec: not rec.offer_date):
            applicant.offer_date = today

    def _check_offer_is_approved(self):
        for applicant in self:
            if applicant.offer_state != "approved":
                raise UserError(_("Job offer actions are only available when the offer is approved."))

    def _get_job_offer_recipient(self):
        self.ensure_one()
        return (
            self.personal_email
            or self.email_from
            or self.partner_id.email
            or self.candidate_id.partner_id.email
            or False
        )

    def action_offer_approve(self):
        result = super().action_offer_approve()
        self._ensure_offer_date()
        return result

    def action_reset_offer_to_draft(self):
        result = super().action_reset_offer_to_draft()
        self.filtered(lambda rec: rec.offer_state == "draft").write({"offer_date": False})
        return result

    def action_print_job_offer(self):
        self.ensure_one()
        self._check_offer_is_approved()
        self._ensure_offer_date()
        return self.env.ref("hr_recruitment_automation.action_report_job_offer").report_action(self)

    def action_send_job_offer(self):
        self.ensure_one()
        self._check_offer_is_approved()
        self._ensure_offer_date()

        recipient = self._get_job_offer_recipient()
        if not recipient:
            raise UserError(_("Candidate email is required before sending the job offer."))

        template = self.env.ref("hr_recruitment_automation.mail_template_job_offer", raise_if_not_found=False)
        if not template:
            raise UserError(_("Job offer email template is missing."))

        template.send_mail(
            self.id,
            force_send=True,
            email_values={"email_to": recipient},
        )
        self.message_post(body=_("Job offer email sent to %(email)s.", email=recipient))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Job Offer Sent"),
                "message": _("The job offer email has been sent to %(email)s.", email=recipient),
                "type": "success",
                "sticky": False,
            },
        }
