# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTransferLitigation(models.TransientModel):
    _name = "qlk.project.transfer.litigation"
    _description = "Transfer Project to Litigation Case"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade")
    client_id = fields.Many2one("res.partner", string="Client", required=True, readonly=True)
    assigned_employee_id = fields.Many2one("hr.employee", string="Assigned Lawyer")
    court_id = fields.Many2one("qlk.casegroup", string="Court", required=True)
    case_main_category_id = fields.Many2one("qlk.maincategory", string="Case Group")
    case_number = fields.Char(string="Court Case Number", required=True)
    case_year = fields.Char(string="Case Year", required=True, default=lambda self: fields.Date.today().strftime("%Y"))
    case_type_id = fields.Many2one("qlk.secondcategory", string="Type of Case")
    filing_date = fields.Date(string="Filing Date", required=True, default=fields.Date.context_today)
    opponent_id = fields.Many2one(
        "res.partner",
        string="Opposing Party",
        required=True,
        domain="[('is_opponent', '=', True)]",
    )
    hearing_date = fields.Date(string="First Hearing Date")
    notes = fields.Text(string="Additional Notes")
    litigation_flow = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
        ],
        string="Proceeding Type",
        required=True,
        default="litigation",
    )

    def action_confirm(self):
        self.ensure_one()
        project = self.project_id
        if project.department != "litigation":
            raise UserError(_("Only litigation projects can be transferred."))
        if project.case_id:
            raise UserError(_("This project is already linked to a litigation case."))

        lawyer = self.assigned_employee_id or project.assigned_employee_ids[:1]
        if not lawyer:
            raise UserError(_("Please assign a lawyer to the project before transferring it to litigation."))

        currency = project.company_id.currency_id
        if not self.case_number.isdigit():
            raise UserError(_("Court case number should contain digits only."))

        case_name = project.name
        if project.client_id:
            if project.client_capacity:
                case_name = _("%(client)s - %(capacity)s", client=project.client_id.name, capacity=project.client_capacity)
            else:
                case_name = project.client_id.name

        case_vals = {
            "name": case_name,
            "name2": project.code or case_name,
            "client_id": project.client_id.id,
            "case_number": int(self.case_number),
            "case_year": self.case_year,
            "employee_id": lawyer.id,
            "currency_id": currency.id,
            "case_group": self.court_id.id,
            "main_category": self.case_main_category_id.id,
            "second_category": self.case_type_id.id,
            "date": self.filing_date,
            "opponent_id": self.opponent_id.id,
            "company_id": project.company_id.id,
            "description": project.description,
            "client_capacity": project.client_capacity,
            "litigation_flow": self.litigation_flow,
        }
        case = self.env["qlk.case"].create(case_vals)

        if self.hearing_date:
            self.env["qlk.hearing"].create(
                {
                    "name": _("Initial Hearing"),
                    "case_id": case.id,
                    "date": self.hearing_date,
                    "case_group": self.court_id.id,
                }
            )

        # update project
        project.write(
            {
            "case_id": case.id,
            "department": "litigation",
            "transfer_ready": False,
            }
        )

        project.message_post(
            body=_(
                "Project transferred to litigation as case %(case)s (court %(court)s).",
                case=case.display_name,
                court=self.court_id.display_name,
            )
        )

        action = self.env.ref("qlk_law.act_open_qlk_case_view", raise_if_not_found=False)
        if action:
            return action.with_context(active_id=case.id, active_ids=[case.id])
        return {"type": "ir.actions.act_window_close"}
