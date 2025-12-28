# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTransferArbitration(models.TransientModel):
    _name = "qlk.project.transfer.arbitration"
    _description = "Transfer Project to Arbitration Case"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade")
    client_id = fields.Many2one("res.partner", string="Client", readonly=True, required=True)
    case_name = fields.Char(string="Case Name", required=True)
    case_number = fields.Char(string="Case Number")
    arbitration_center = fields.Char(string="Arbitration Center")
    assigned_employee_id = fields.Many2one("hr.employee", string="Responsible Lawyer", required=True)
    claimant_id = fields.Many2one("res.partner", string="Claimant", required=True)
    respondent_id = fields.Many2one("res.partner", string="Respondent")
    start_date = fields.Date(string="Start Date", default=fields.Date.context_today)
    notes = fields.Text(string="Notes")

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if not self.project_id:
            return
        self.client_id = self.project_id.client_id.id
        self.claimant_id = self.project_id.client_id.id
        self.case_name = self.project_id.name
        if not self.assigned_employee_id and self.project_id.assigned_employee_ids:
            self.assigned_employee_id = self.project_id.assigned_employee_ids[:1]

    def action_confirm(self):
        self.ensure_one()
        project = self.project_id
        if project.department != "arbitration":
            raise UserError(_("Only arbitration projects can be transferred."))
        if project.arbitration_case_id:
            raise UserError(_("This project is already linked to an arbitration case."))

        case_vals = {
            "name": self.case_name,
            "case_number": self.case_number,
            "arbitration_center": self.arbitration_center,
            "responsible_employee_id": self.assigned_employee_id.id,
            "claimant_id": self.claimant_id.id,
            "respondent_id": self.respondent_id.id if self.respondent_id else False,
            "start_date": self.start_date,
            "project_id": project.id,
            "notes": self.notes,
            "client_capacity": project.client_capacity,
        }
        case = self.env["qlk.arbitration.case"].create(case_vals)

        project.write(
            {
                "arbitration_case_id": case.id,
                "department": "arbitration",
                "transfer_ready": False,
            }
        )
        project.message_post(
            body=_("Project linked to arbitration case %(case)s.", case=case.display_name),
        )

        action = self.env.ref("qlk_arbitration.action_arbitration_case", raise_if_not_found=False)
        if action:
            return action.with_context(active_id=case.id, active_ids=[case.id])
        return {"type": "ir.actions.act_window_close"}
