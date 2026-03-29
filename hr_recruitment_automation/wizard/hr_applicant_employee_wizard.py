from odoo import fields, models


class HrApplicantEmployeeCreateWizard(models.TransientModel):
    _name = "hr.applicant.employee.create.wizard"
    _description = "Create Employee From Applicant Wizard"

    applicant_id = fields.Many2one("hr.applicant", required=True, readonly=True)

    def action_confirm_create_employee(self):
        self.ensure_one()
        return self.applicant_id.action_create_employee_and_contract()
