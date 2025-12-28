# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

CORPORATE_SERVICE_SELECTION = [
    ("incorporation", "Company Incorporation"),
    ("contract", "Commercial Contract"),
    ("trademark", "Trademark Registration"),
    ("advisory", "Ongoing Advisory"),
    ("other", "Other"),
]

class ProjectTransferCorporate(models.TransientModel):
    _name = "qlk.project.transfer.corporate"
    _description = "Transfer Project to Corporate Case"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade")
    client_id = fields.Many2one("res.partner", string="Client", required=True, readonly=True)
    assigned_employee_id = fields.Many2one("hr.employee", string="Responsible Lawyer", required=True)
    case_name = fields.Char(string="Case Name", required=True)
    service_type = fields.Selection(CORPORATE_SERVICE_SELECTION, string="Service Type", required=True, default="incorporation")
    agreement_hours = fields.Float(string="Agreement Hours")
    agreement_start_date = fields.Date(string="Agreement Start Date")
    agreement_end_date = fields.Date(string="Agreement End Date")
    notes = fields.Text(string="Notes")

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if not self.project_id:
            return
        self.client_id = self.project_id.client_id.id
        self.case_name = self.project_id.name
        if not self.assigned_employee_id and self.project_id.assigned_employee_ids:
            self.assigned_employee_id = self.project_id.assigned_employee_ids[:1]

    def action_confirm(self):
        self.ensure_one()
        project = self.project_id
        if project.department != "corporate":
            raise UserError(_("Only corporate projects can be transferred."))
        if project.corporate_case_id:
            raise UserError(_("This project is already linked to a corporate case."))

        case_vals = {
            "name": self.case_name,
            "client_id": self.client_id.id,
            "service_type": self.service_type,
            "responsible_employee_id": self.assigned_employee_id.id,
            "project_id": project.id,
            "agreement_hours": self.agreement_hours,
            "agreement_start_date": self.agreement_start_date,
            "agreement_end_date": self.agreement_end_date,
            "notes": self.notes,
            "client_capacity": project.client_capacity,
        }
        case = self.env["qlk.corporate.case"].create(case_vals)

        project.write(
            {
                "corporate_case_id": case.id,
                "department": "corporate",
                "transfer_ready": False,
            }
        )
        project.message_post(
            body=_("Project linked to corporate case %(case)s.", case=case.display_name),
        )

        action = self.env.ref("qlk_corporate.action_corporate_case", raise_if_not_found=False)
        if action:
            return action.with_context(active_id=case.id, active_ids=[case.id])
        return {"type": "ir.actions.act_window_close"}
