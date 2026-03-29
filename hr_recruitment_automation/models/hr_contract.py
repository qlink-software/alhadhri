from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    # هذه الحقول لحفظ مكونات البدل ضمن العقد الذي يتم إنشاؤه تلقائيًا من التوظيف.
    housing_allowance = fields.Monetary(string="Housing Allowance", required=True)
    transportation_allowance = fields.Monetary(string="Transportation Allowance", required=True)
    phone_allowance = fields.Monetary(string="Phone Allowance", required=True)
    other_allowance = fields.Monetary(string="Other Allowance", required=True)
    salary_type = fields.Selection(
        [("fixed", "Fixed")],
        string="Salary Type",
        default="fixed",
        required=True,
    )
    payroll_start_date = fields.Date(string="Payroll Start Date", required=True)
    bank_name = fields.Char(string="Bank Name", required=True)
    bank_account_number = fields.Char(string="Bank Account Number", required=True)
