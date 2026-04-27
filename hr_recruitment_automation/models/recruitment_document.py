import secrets
import string

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RecruitmentDocumentPackage(models.Model):
    _name = "hr.recruitment.document.package"
    _description = "Recruitment Document Package"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Reference", required=True, copy=False, default=lambda self: _("New"))
    applicant_id = fields.Many2one("hr.applicant", string="Applicant", required=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, ondelete="cascade")
    contract_id = fields.Many2one("hr.contract", string="Contract", ondelete="set null")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("signed", "Signed"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )

    # هذا التوكن يستخدم لتوقيع روابط موافقة/رفض الموظف عبر البريد الإلكتروني.
    access_token = fields.Char(string="Access Token", copy=False, default=lambda self: secrets.token_urlsafe(24), index=True)
    approve_url = fields.Char(string="Approve URL", compute="_compute_access_urls")
    reject_url = fields.Char(string="Reject URL", compute="_compute_access_urls")

    manager_reject_reason = fields.Text(string="Manager Rejection Reason")
    approval_user_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    approval_date = fields.Datetime(string="Approval Date", readonly=True, copy=False)
    signed_date = fields.Datetime(string="Signed Date", readonly=True, copy=False)
    employee_response_date = fields.Datetime(string="Employee Response Date", copy=False)
    access_email_sent = fields.Boolean(string="Access Email Sent", copy=False)

    # هذه النصوص قابلة للتعديل اليدوي قبل الإرسال النهائي.
    contract_body_ar = fields.Html(string="Employment Contract (AR)")
    contract_body_en = fields.Html(string="Employment Contract (EN)")
    nda_body_ar = fields.Html(string="NDA (AR)")
    nda_body_en = fields.Html(string="NDA (EN)")

    def init(self):
        # هذا التحديث يحافظ على توافق السجلات القديمة مع الـ workflow الجديد عند الترقية.
        self.env.cr.execute(
            """
            UPDATE hr_recruitment_document_package
               SET state = CASE state
                   WHEN 'waiting_manager_approval' THEN 'under_review'
                   WHEN 'manager_rejected' THEN 'rejected'
                   WHEN 'employee_pending' THEN 'approved'
                   WHEN 'employee_accepted' THEN 'signed'
                   WHEN 'employee_rejected' THEN 'rejected'
                   ELSE state
               END
             WHERE state IN (
                 'waiting_manager_approval',
                 'manager_rejected',
                 'employee_pending',
                 'employee_accepted',
                 'employee_rejected'
             )
            """
        )

    @api.depends("access_token")
    def _compute_access_urls(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for package in self:
            package.approve_url = f"{base_url}/recruitment/document/approve/{package.access_token}" if package.access_token else False
            package.reject_url = f"{base_url}/recruitment/document/reject/{package.access_token}" if package.access_token else False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == _("New"):
                record.name = f"DOC/{record.id:05d}"
        return records

    def _check_managing_partner_access(self):
        if not self.env.user.has_group("qlk_management.group_hr_manager"):
            raise UserError(_("Only Managing Partner can approve or reject document packages."))

    def _generate_password(self, length=12):
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _i in range(length))

    def _ensure_portal_user(self):
        self.ensure_one()
        applicant = self.applicant_id
        employee = self.employee_id

        login = applicant.system_username or applicant.proposed_work_email or employee.work_email or applicant.personal_email
        if not login:
            raise UserError(_("System username or work/personal email is required to create employee access."))

        partner = employee.work_contact_id or applicant.partner_id or applicant.candidate_id.partner_id
        if not partner:
            partner = self.env["res.partner"].sudo().create(
                {
                    "name": employee.name,
                    "email": applicant.personal_email or applicant.proposed_work_email,
                    "phone": applicant.personal_phone,
                }
            )
            employee.work_contact_id = partner.id

        user = employee.user_id
        if not user:
            user = self.env["res.users"].sudo().search([("login", "=", login)], limit=1)

        portal_group = self.env.ref("base.group_portal")
        generated_password = self._generate_password()

        if user:
            user.sudo().write(
                {
                    "active": True,
                    "login": login,
                    "email": applicant.proposed_work_email or applicant.personal_email or user.email,
                    "password": generated_password,
                }
            )
        else:
            user = self.env["res.users"].sudo().create(
                {
                    "name": employee.name,
                    "login": login,
                    "email": applicant.proposed_work_email or applicant.personal_email,
                    "partner_id": partner.id,
                    "password": generated_password,
                    "groups_id": [(6, 0, [portal_group.id])],
                    "share": True,
                }
            )

        # فرض صلاحية Portal فقط حسب المتطلب.
        user.sudo().write({"groups_id": [(6, 0, [portal_group.id])]})
        employee.user_id = user.id

        return user, generated_password

    def _send_template(self, xmlid, email_to=None, context_data=None):
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        ctx = dict(self.env.context)
        if context_data:
            ctx.update(context_data)
        email_values = {}
        if email_to:
            email_values["email_to"] = email_to
        template.with_context(ctx).send_mail(self.id, force_send=True, email_values=email_values)

    def action_send_for_approval(self):
        for package in self:
            if package.state != "draft":
                raise UserError(_("Documents can only be sent for approval from Draft."))
            package.state = "under_review"
            recipients = package.env.ref("qlk_management.group_hr_manager").users.filtered(lambda u: u.email)
            if recipients:
                package._send_template(
                    "hr_recruitment_automation.mail_template_documents_for_manager_approval",
                    email_to=",".join(recipients.mapped("email")),
                )

    def action_approve(self):
        for package in self:
            package._check_managing_partner_access()
            if package.state != "under_review":
                raise UserError(_("Documents can only be approved from Under Review."))
            package.write(
                {
                    "state": "approved",
                    "manager_reject_reason": False,
                    "approval_user_id": self.env.user.id,
                    "approval_date": fields.Datetime.now(),
                }
            )
            employee_email = package.applicant_id.personal_email or package.employee_id.private_email
            if employee_email:
                package._send_template(
                    "hr_recruitment_automation.mail_template_documents_for_employee_approval",
                    email_to=employee_email,
                )

    def action_sign(self):
        for package in self:
            if package.state != "approved":
                raise UserError(_("Documents cannot be signed before approval."))
            package.state = "signed"
            package.signed_date = fields.Datetime.now()
            package.employee_response_date = fields.Datetime.now()

            user, generated_password = package._ensure_portal_user()
            login_url = package.env["ir.config_parameter"].sudo().get_param("web.base.url", "") + "/web/login"
            package._send_template(
                "hr_recruitment_automation.mail_template_system_access",
                email_to=user.email,
                context_data={
                    "generated_password": generated_password,
                    "login_url": login_url,
                    "generated_login": user.login,
                },
            )
            package.access_email_sent = True

    # هذه الدوال تُترك للتوافق مع الأزرار/الروابط القديمة داخل الموديول.
    def action_send_to_manager(self):
        return self.action_send_for_approval()

    def action_manager_approve(self):
        return self.action_approve()

    def action_manager_reject(self):
        for package in self:
            package._check_managing_partner_access()
            if package.state not in ("under_review", "approved"):
                raise UserError(_("Documents can only be rejected while under review or after approval."))
            package.state = "rejected"

    def action_employee_accept(self):
        return self.action_sign()

    def action_employee_reject(self):
        for package in self:
            if package.state not in ("approved", "signed"):
                raise UserError(_("Employee rejection is only allowed after approval."))
            package.state = "rejected"
            package.employee_response_date = fields.Datetime.now()

    def action_reset_to_draft(self):
        self.write(
            {
                "state": "draft",
                "manager_reject_reason": False,
                "approval_user_id": False,
                "approval_date": False,
                "signed_date": False,
                "employee_response_date": False,
                "access_email_sent": False,
            }
        )
