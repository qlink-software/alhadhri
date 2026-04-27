from passlib.hash import pbkdf2_sha512
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    # -------------------------------------------------------------------------
    # Job Offer Workflow
    # -------------------------------------------------------------------------
    offer_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_manager_approval", "Waiting Manager Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("accepted", "Accepted"),
        ],
        string="Job Offer State",
        default="draft",
        tracking=True,
        copy=False,
    )
    offer_reject_reason = fields.Text(string="Offer Rejection Reason", copy=False)
    can_manage_offer = fields.Boolean(compute="_compute_can_manage_offer")

    # -------------------------------------------------------------------------
    # Personal Information
    # -------------------------------------------------------------------------
    recruitment_full_name = fields.Char(string="Full Name", tracking=True, )
    nationality_id = fields.Many2one("res.country", string="Nationality", )
    date_of_birth = fields.Date(string="Date of Birth", )
    recruitment_gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
        
    )
    qid_passport_number = fields.Char(string="QID/Passport Number",)
    marital_status = fields.Selection(
        [
            ("single", "Single"),
            ("married", "Married"),
            ("cohabitant", "Cohabitant"),
            ("widower", "Widower"),
            ("divorced", "Divorced"),
        ],
        string="Marital Status",
        default="single",
        
    )
    personal_phone = fields.Char(string="Personal Phone", )
    personal_email = fields.Char(string="Personal Email", )
    home_address = fields.Text(string="Home Address", )

    # -------------------------------------------------------------------------
    # Employment Information
    # -------------------------------------------------------------------------
    employment_type = fields.Selection(
        [("full_time", "Full-time"), ("part_time", "Part-time")],
        string="Employment Type",
        default="full_time",
        
    )
    reporting_manager_id = fields.Many2one("hr.employee", string="Reporting Manager", )
    office_location_id = fields.Many2one("hr.work.location", string="Office Location", )
    proposed_work_email = fields.Char(string="Work Email", )
    system_username = fields.Char(string="System Username",)
    system_password_input = fields.Char(string="System Password", copy=False)
    system_password_hash = fields.Char(string="System Password Hash", readonly=True, copy=False)

    # -------------------------------------------------------------------------
    # Compensation
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    basic_salary = fields.Monetary(string="Basic Salary", currency_field="currency_id", )
    housing_allowance = fields.Monetary(string="Housing Allowance", currency_field="currency_id", )
    transportation_allowance = fields.Monetary(string="Transportation Allowance", currency_field="currency_id", )
    phone_allowance = fields.Monetary(string="Phone Allowance", currency_field="currency_id", )
    other_allowance = fields.Monetary(string="Other Allowance", currency_field="currency_id", )
    bank_name = fields.Char(string="Bank Name", )
    bank_account_number = fields.Char(string="Bank Account Number", )
    payroll_start_date = fields.Date(string="Payroll Start Date", )
    salary_type = fields.Selection(
        [("fixed", "Fixed")],
        string="Salary Type",
        default="fixed",
        
    )

    # -------------------------------------------------------------------------
    # Attachments
    # -------------------------------------------------------------------------
    qid_passport_copy = fields.Binary(string="QID/Passport Copy", attachment=True,)
    qid_passport_filename = fields.Char(string="QID/Passport Filename")
    cv_copy = fields.Binary(string="CV", attachment=True, )
    cv_filename = fields.Char(string="CV Filename")
    certificates_copy = fields.Binary(string="Certificates", attachment=True, )
    certificates_filename = fields.Char(string="Certificates Filename")
    visa_copy = fields.Binary(string="Visa", attachment=True,)
    visa_filename = fields.Char(string="Visa Filename")
    other_document_ids = fields.Many2many(
        "ir.attachment",
        "hr_applicant_other_document_rel",
        "applicant_id",
        "attachment_id",
        string="Other Documents",
    )

    # -------------------------------------------------------------------------
    # Generated records
    # -------------------------------------------------------------------------
    employee_created_id = fields.Many2one("hr.employee", string="Generated Employee", copy=False, readonly=True)
    generated_contract_id = fields.Many2one("hr.contract", string="Generated Contract", copy=False, readonly=True)
    joining_email_sent = fields.Boolean(string="Joining Email Sent", copy=False, readonly=True)
    document_package_ids = fields.One2many("hr.recruitment.document.package", "applicant_id", string="Document Packages")
    document_package_count = fields.Integer(compute="_compute_document_package_count")

    @api.constrains("system_password_hash")
    def _check_required_system_password(self):
        for applicant in self:
            if not applicant.system_password_hash:
                raise ValidationError(_("System Password is required."))

    @api.depends_context("uid")
    def _compute_can_manage_offer(self):
        has_permission = self.env.user.has_group("qlk_management.group_hr_manager")
        for applicant in self:
            applicant.can_manage_offer = has_permission

    @api.depends("document_package_ids")
    def _compute_document_package_count(self):
        for applicant in self:
            applicant.document_package_count = len(applicant.document_package_ids)

    def _hash_password_in_vals(self, vals):
        # تخزين كلمة المرور بصورة مشفرة فقط وعدم الاحتفاظ بالنص الصريح.
        password = vals.get("system_password_input")
        if password:
            vals["system_password_hash"] = pbkdf2_sha512.hash(password)
            vals["system_password_input"] = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._hash_password_in_vals(vals)
        records = super().create(vals_list)
        for record in records:
            if record.recruitment_full_name and not record.partner_name:
                record.partner_name = record.recruitment_full_name
        return records

    def write(self, vals):
        self._hash_password_in_vals(vals)
        result = super().write(vals)
        if vals.get("recruitment_full_name"):
            for record in self:
                if record.recruitment_full_name:
                    record.partner_name = record.recruitment_full_name
        return result

    # -------------------------------------------------------------------------
    # Workflow Actions
    # -------------------------------------------------------------------------
    def action_send_to_manager(self):
        for applicant in self:
            applicant.offer_state = "waiting_manager_approval"

    def _check_manager_approval_permission(self):
        if not self.env.user.has_group("qlk_management.group_hr_manager"):
            raise UserError(_("Only Managing Partner can approve or reject job offers."))

    def action_offer_approve(self):
        self._check_manager_approval_permission()
        for applicant in self:
            applicant.offer_state = "approved"
            applicant.offer_reject_reason = False

    def action_reset_offer_to_draft(self):
        for applicant in self:
            if applicant.offer_state == "approved":
                applicant.write({
                    "offer_state": "draft",
                    "offer_reject_reason": False,
                    "active": True,
                })

    def action_open_offer_reject_wizard(self):
        self._check_manager_approval_permission()
        self.ensure_one()
        return {
            "name": _("Reject Job Offer"),
            "type": "ir.actions.act_window",
            "res_model": "hr.applicant.offer.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_applicant_id": self.id},
        }

    def action_mark_offer_rejected(self, reason=None):
        self._check_manager_approval_permission()
        for applicant in self:
            applicant.write(
                {
                    "offer_state": "rejected",
                    "offer_reject_reason": reason or applicant.offer_reject_reason,
                    "active": False,
                }
            )

    def action_mark_offer_accepted(self):
        self.ensure_one()
        if self.offer_state != "approved":
            raise UserError(_("Job offer must be approved before marking as accepted."))
        self.offer_state = "accepted"
        return {
            "name": _("Create Employee"),
            "type": "ir.actions.act_window",
            "res_model": "hr.applicant.employee.create.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_applicant_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Employee & Contract Creation
    # -------------------------------------------------------------------------
    def _ensure_recruitment_partner(self):
        self.ensure_one()
        partner = self.partner_id or self.candidate_id.partner_id
        if partner:
            return partner

        partner = self.env["res.partner"].create(
            {
                "name": self.recruitment_full_name or self.partner_name,
                "email": self.personal_email or self.email_from,
                "phone": self.personal_phone or self.partner_phone,
                "street": self.home_address,
                "is_company": False,
            }
        )
        if self.candidate_id:
            self.candidate_id.partner_id = partner.id
        return partner

    def _prepare_employee_vals(self, partner):
        self.ensure_one()
        joining_date = self.payroll_start_date or fields.Date.context_today(self)
        return {
            "name": self.recruitment_full_name or self.partner_name,
            "work_contact_id": partner.id,
            "private_street": self.home_address,
            "private_email": self.personal_email,
            "private_phone": self.personal_phone,
            "country_id": self.nationality_id.id,
            "birthday": self.date_of_birth,
            "gender": self.recruitment_gender,
            "marital": self.marital_status or "single",
            "identification_id": self.qid_passport_number,
            "passport_id": self.qid_passport_number,
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "job_title": self.job_id.name,
            "parent_id": self.reporting_manager_id.id,
            "work_location_id": self.office_location_id.id,
            "work_email": self.proposed_work_email or self.email_from,
            "phone": self.personal_phone,
            "employment_type": self.employment_type,
            "date_of_joining": joining_date,
            "status": "active",
            "applicant_origin_id": self.id,
            "active": True,
        }

    def _prepare_contract_vals(self, employee):
        self.ensure_one()
        contract_type = self.env["hr.contract.type"].search([], limit=1)
        start_date = self.payroll_start_date or fields.Date.context_today(self)
        end_date = start_date + relativedelta(years=1, days=-1)
        today = fields.Date.context_today(self)
        state = "open" if start_date <= today else "draft"
        kanban_state = "normal" if start_date <= today else "done"
        return {
            "name": f"{employee.name} Contract",
            "employee_id": employee.id,
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "date_start": start_date,
            "date_end": end_date,
            "payroll_start_date": start_date,
            "wage": self.basic_salary or 0.0,
            "housing_allowance": self.housing_allowance,
            "transportation_allowance": self.transportation_allowance,
            "phone_allowance": self.phone_allowance,
            "other_allowance": self.other_allowance,
            "bank_name": self.bank_name,
            "bank_account_number": self.bank_account_number,
            "salary_type": self.salary_type,
            "contract_type_id": contract_type.id,
            "state": state,
            "kanban_state": kanban_state,
        }

    def _get_or_create_generated_contract(self, employee):
        self.ensure_one()
        contract = self.generated_contract_id.exists() if self.generated_contract_id else self.env["hr.contract"]
        contract_vals = self._prepare_contract_vals(employee)
        if contract:
            contract.sudo().write(contract_vals)
        else:
            contract = self.env["hr.contract"].sudo().create(contract_vals)
            self.generated_contract_id = contract.id
        return contract

    def _send_joining_email(self, employee, contract):
        self.ensure_one()
        if self.joining_email_sent:
            return
        recipient = self.personal_email or self.proposed_work_email or employee.work_email or employee.private_email
        if not recipient:
            return
        template = self.env.ref("hr_recruitment_automation.mail_template_employee_joining_notice", raise_if_not_found=False)
        if not template:
            return
        login_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") + "/web/login"
        template.with_context(login_url=login_url).send_mail(
            self.id,
            force_send=True,
            email_values={"email_to": recipient},
        )
        self.joining_email_sent = True
        employee.message_post(body=_("Joining email sent to %(email)s.", email=recipient))
        contract.message_post(body=_("Joining email sent to %(email)s.", email=recipient))

    def _copy_attachments_to_employee(self, employee):
        self.ensure_one()
        Attachment = self.env["ir.attachment"].sudo()

        source_attachments = Attachment.search([
            ("res_model", "in", ["hr.applicant", "hr.candidate"]),
            ("res_id", "in", [self.id, self.candidate_id.id]),
        ])
        source_attachments |= self.other_document_ids

        for attachment in source_attachments:
            attachment.copy({"res_model": "hr.employee", "res_id": employee.id})

    def _ensure_annual_leave_allocation(self, employee, start_date):
        annual_type = self.env.ref("hr_recruitment_automation.leave_type_annual", raise_if_not_found=False)
        annual_plan = self.env.ref("hr_recruitment_automation.leave_accrual_plan_annual", raise_if_not_found=False)
        if not annual_type or not annual_plan:
            return

        existing = self.env["hr.leave.allocation"].search_count(
            [
                ("employee_id", "=", employee.id),
                ("holiday_status_id", "=", annual_type.id),
                ("allocation_type", "=", "accrual"),
            ]
        )
        if existing:
            return

        allocation = self.env["hr.leave.allocation"].sudo().create(
            {
                "employee_id": employee.id,
                "holiday_status_id": annual_type.id,
                "allocation_type": "accrual",
                "accrual_plan_id": annual_plan.id,
                "date_from": start_date,
            }
        )
        if allocation.state != "validate":
            allocation.action_validate()

    def _get_contract_form_action(self, contract):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("hr_contract.action_hr_contract")
        action.update(
            {
                "res_id": contract.id,
                "view_mode": "form",
                "views": [(False, "form")],
            }
        )
        return action

    def action_create_employee_and_contract(self):
        self.ensure_one()

        if self.employee_created_id:
            contract = self._get_or_create_generated_contract(self.employee_created_id)
            self._send_joining_email(self.employee_created_id, contract)
            return self._get_contract_form_action(contract)

        partner = self._ensure_recruitment_partner()
        employee_vals = self._prepare_employee_vals(partner)

        employee = self.env["hr.employee"].sudo().create(employee_vals)
        employee.recruitment_employee_code = employee._generate_recruitment_employee_code()

        if self.candidate_id:
            self.candidate_id.employee_id = employee.id

        self.write(
            {
                "employee_created_id": employee.id,
                "offer_state": "accepted",
                "date_closed": fields.Datetime.now(),
                "active": True,
            }
        )

        self._copy_attachments_to_employee(employee)

        contract = self._get_or_create_generated_contract(employee)

        self._ensure_annual_leave_allocation(employee, contract.date_start)
        self._send_joining_email(employee, contract)

        return self._get_contract_form_action(contract)

    # -------------------------------------------------------------------------
    # Document Generation
    # -------------------------------------------------------------------------
    def _prepare_document_bodies(self, employee):
        self.ensure_one()
        employee_code = employee.recruitment_employee_code or "-"
        company_name = self.company_id.name or ""
        work_email = self.proposed_work_email or employee.work_email or ""

        contract_ar = f"""
<p><strong>عقد عمل</strong></p>
<p>الطرف الأول: {company_name}</p>
<p>الطرف الثاني: {employee.name}</p>
<p>رقم الموظف: {employee_code}</p>
<p>الراتب الأساسي: {self.basic_salary or 0.0}</p>
<p>بدل السكن: {self.housing_allowance or 0.0} | بدل النقل: {self.transportation_allowance or 0.0}</p>
<p>تاريخ بداية العمل: {self.payroll_start_date or fields.Date.context_today(self)}</p>
"""

        contract_en = f"""
<p><strong>Employment Contract</strong></p>
<p>First Party: {company_name}</p>
<p>Second Party: {employee.name}</p>
<p>Employee Code: {employee_code}</p>
<p>Basic Salary: {self.basic_salary or 0.0}</p>
<p>Allowances: Housing {self.housing_allowance or 0.0}, Transportation {self.transportation_allowance or 0.0}</p>
<p>Employment Start Date: {self.payroll_start_date or fields.Date.context_today(self)}</p>
<p>Official Work Email: {work_email}</p>
"""

        nda_ar = f"""
<p><strong>اتفاقية عدم إفصاح (NDA)</strong></p>
<p>يلتزم الموظف/ـة {employee.name} بالحفاظ على سرية جميع المعلومات المتعلقة بأعمال {company_name}.</p>
"""

        nda_en = f"""
<p><strong>Non-Disclosure Agreement (NDA)</strong></p>
<p>The employee {employee.name} agrees to keep all confidential information related to {company_name} protected.</p>
"""

        return {
            "contract_body_ar": contract_ar,
            "contract_body_en": contract_en,
            "nda_body_ar": nda_ar,
            "nda_body_en": nda_en,
        }

    def action_generate_documents(self):
        self.ensure_one()
        if not self.employee_created_id:
            raise UserError(_("Employee must be created before generating documents."))

        vals = {
            "applicant_id": self.id,
            "employee_id": self.employee_created_id.id,
            "contract_id": self.generated_contract_id.id,
        }
        vals.update(self._prepare_document_bodies(self.employee_created_id))
        package = self.env["hr.recruitment.document.package"].create(vals)

        return {
            "type": "ir.actions.act_window",
            "name": _("Document Package"),
            "res_model": "hr.recruitment.document.package",
            "view_mode": "form",
            "res_id": package.id,
        }

    # -------------------------------------------------------------------------
    # Utility actions
    # -------------------------------------------------------------------------
    def action_open_generated_employee(self):
        self.ensure_one()
        if not self.employee_created_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Employee"),
            "res_model": "hr.employee",
            "view_mode": "form",
            "res_id": self.employee_created_id.id,
        }

    def action_open_generated_contract(self):
        self.ensure_one()
        if not self.generated_contract_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Contract"),
            "res_model": "hr.contract",
            "view_mode": "form",
            "res_id": self.generated_contract_id.id,
        }

    def action_open_document_packages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Document Packages"),
            "res_model": "hr.recruitment.document.package",
            "view_mode": "list,form",
            "domain": [("applicant_id", "=", self.id)],
            "context": {"default_applicant_id": self.id, "default_employee_id": self.employee_created_id.id},
        }
