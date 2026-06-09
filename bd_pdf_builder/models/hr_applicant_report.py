# -*- coding: utf-8 -*-
from odoo import fields, models


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    bd_nationality = fields.Char(string="Nationality")
    bd_passport_no = fields.Char(string="Passport Number")
    bd_qid_no = fields.Char(string="QID Number")
    bd_date_of_birth = fields.Date(string="Date of Birth")
    bd_marital_status = fields.Char(string="Marital Status")
    bd_address = fields.Char(string="Permanent Address")
    bd_contract_start_date = fields.Date(string="Employment Start Date")
    bd_basic_salary = fields.Float(string="Basic Salary")
    bd_housing_allowance = fields.Float(string="Housing Allowance")
    bd_transportation_allowance = fields.Float(string="Transportation Allowance")
    bd_phone_allowance = fields.Float(string="Phone Allowance")
    bd_other_allowance = fields.Float(string="Other Allowance")
    bd_annual_leave_days = fields.Integer(string="Annual Leave Days", default=21)
    bd_probation_period = fields.Char(string="Probation Period", default="Six months as per labor law")
    bd_ticket_policy = fields.Char(string="Ticket Policy", default="Economy ticket to home country every 2 years")
    bd_contract_duration = fields.Char(string="Contract Duration", default="Indefinite")

    def _bd_report_action(self, xmlid):
        self.ensure_one()
        return self.env.ref(xmlid).report_action(self)

    def action_print_employee_nda_pdf(self):
        return self._bd_report_action("bd_pdf_builder.action_hr_applicant_nda_pdf")

    def action_print_employee_offer_letter_pdf(self):
        return self._bd_report_action("bd_pdf_builder.action_hr_applicant_offer_letter_pdf")

    def action_print_employment_contract_pdf(self):
        return self._bd_report_action("bd_pdf_builder.action_hr_applicant_employment_contract_pdf")
