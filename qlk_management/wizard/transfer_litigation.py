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
        """Create the court case and switch the project from pre-litigation to litigation."""
        self.ensure_one()
        project = self.project_id
        if project.project_type != "litigation":
            raise UserError(_("Only litigation projects can be transferred to the court pipeline."))
        if project.case_id:
            raise UserError(_("This project is already linked to a litigation case."))
        if project.litigation_stage != "pre":
            raise UserError(_("Transfer to Litigation is available only for pre-litigation projects."))

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
        values = {
            "case_id": case.id,
            "department": "litigation",
            "project_type": "litigation",
            "litigation_stage": "court",
            "litigation_stage_code": project.litigation_stage_code or "F",
            "litigation_stage_iteration": 0,
            "transfer_ready": False,
        }
        if not project.litigation_case_number and project.client_id:
            next_number = project._next_litigation_case_number(project.client_id.id)
            values["litigation_case_number"] = next_number
            values.setdefault("case_sequence", next_number)
        project.write(values)
        project._ensure_litigation_workflow()
        translation_line = project.stage_line_ids.filtered(lambda line: line.stage_key == "translation")[:1]
        if translation_line:
            translation_line.write(
                {
                    "progress": 100.0,
                    "comment": _("Completed automatically when the project was transferred to litigation."),
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
