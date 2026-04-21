# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTransferLitigation(models.TransientModel):
    _name = "qlk.project.transfer.litigation"
    _description = "Transfer Project to Litigation Case"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade")
    client_id = fields.Many2one("res.partner", string="Client", required=True, readonly=True)
    available_litigation_level_ids = fields.Many2many(
        "litigation.level",
        compute="_compute_available_litigation_level_ids",
    )
    litigation_level_id = fields.Many2one(
        "litigation.level",
        string="درجة التقاضي",
        required=True,
        domain="[('id', 'in', available_litigation_level_ids)]",
    )
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

    @api.depends(
        "project_id",
        "project_id.allow_multiple_cases_per_level",
        "project_id.case_ids.litigation_level_id",
        "project_id.litigation_level_ids",
    )
    def _compute_available_litigation_level_ids(self):
        for wizard in self:
            wizard.available_litigation_level_ids = (
                wizard.project_id._get_available_litigation_levels()
                if wizard.project_id
                else False
            )

    def action_confirm(self):
        """Create the court case and switch the project from pre-litigation to litigation."""
        self.ensure_one()
        project = self.project_id
        if project.project_type != "litigation":
            raise UserError(_("Only litigation projects can be transferred to the court pipeline."))
        project._ensure_litigation_case_available()
        if project.litigation_stage != "pre":
            raise UserError(_("Transfer to Litigation is available only for pre-litigation projects."))
        if self.litigation_level_id not in project._get_available_litigation_levels():
            raise UserError(_("درجة التقاضي المختارة غير متاحة لهذا المشروع."))

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

        case_vals = project._prepare_litigation_case_vals(self.litigation_level_id)
        case_vals.update(
            {
                "name": case_name,
                "name2": project.code or case_name,
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
            }
        )
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
            "department": "litigation",
            "project_type": "litigation",
            "litigation_stage": "court",
            "litigation_stage_code": self.litigation_level_id.code or project.litigation_stage_code or "F",
            "litigation_stage_iteration": 0,
            "transfer_ready": False,
        }
        if not project.litigation_case_number and project.client_id:
            next_number = project._next_litigation_case_number(project.client_id.id)
            values["litigation_case_number"] = next_number
            values.setdefault("case_sequence", next_number)
        if not project.case_id:
            values["case_id"] = case.id
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
            result = action.read()[0]
            result["res_id"] = case.id
            result["view_mode"] = "form"
            result["views"] = [(False, "form")]
            return result
        return {"type": "ir.actions.act_window_close"}


class ProjectCreateLitigationCase(models.TransientModel):
    _name = "qlk.project.create.litigation.case"
    _description = "Create Litigation Case from Project"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade", readonly=True)
    client_id = fields.Many2one("res.partner", string="Client", required=True, readonly=True)
    available_litigation_level_ids = fields.Many2many(
        "litigation.level",
        compute="_compute_available_litigation_level_ids",
    )
    litigation_level_id = fields.Many2one(
        "litigation.level",
        string="درجة التقاضي",
        required=True,
        domain="[('id', 'in', available_litigation_level_ids)]",
    )
    assigned_employee_id = fields.Many2one("hr.employee", string="Assigned Lawyer")
    court_id = fields.Many2one("qlk.casegroup", string="Court")
    case_main_category_id = fields.Many2one("qlk.maincategory", string="Case Group")
    case_number = fields.Char(string="Court Case Number")
    case_year = fields.Char(string="Case Year", default=lambda self: fields.Date.today().strftime("%Y"))
    case_type_id = fields.Many2one("qlk.secondcategory", string="Type of Case")
    filing_date = fields.Date(string="Filing Date", default=fields.Date.context_today)
    opponent_id = fields.Many2one(
        "res.partner",
        string="Opposing Party",
        domain="[('is_opponent', '=', True)]",
    )
    notes = fields.Text(string="Additional Notes")

    @api.depends(
        "project_id",
        "project_id.allow_multiple_cases_per_level",
        "project_id.case_ids.litigation_level_id",
        "project_id.litigation_level_ids",
    )
    def _compute_available_litigation_level_ids(self):
        for wizard in self:
            wizard.available_litigation_level_ids = (
                wizard.project_id._get_available_litigation_levels()
                if wizard.project_id
                else False
            )

    def action_confirm(self):
        self.ensure_one()
        project = self.project_id
        if project.project_type != "litigation":
            raise UserError(_("Only litigation projects can create litigation cases."))
        if project.litigation_stage != "court":
            raise UserError(_("Litigation cases can be created only in the Litigation stage."))
        project._ensure_litigation_case_available()
        if self.litigation_level_id not in project._get_available_litigation_levels():
            raise UserError(_("درجة التقاضي المختارة غير متاحة لهذا المشروع."))
        self.env["qlk.case"].check_access_rights("create")

        lawyer = self.assigned_employee_id or project._get_primary_employee()
        case_vals = project._prepare_litigation_case_vals(self.litigation_level_id)
        if not case_vals:
            raise UserError(_("Unable to prepare a litigation case from this project."))
        case_vals.setdefault("state", "study")
        if lawyer:
            case_vals["employee_id"] = lawyer.id
        if self.court_id:
            case_vals["case_group"] = self.court_id.id
        if self.case_main_category_id:
            case_vals["main_category"] = self.case_main_category_id.id
        if self.case_type_id:
            case_vals["second_category"] = self.case_type_id.id
        if self.filing_date:
            case_vals["date"] = self.filing_date
        if self.opponent_id:
            case_vals["opponent_id"] = self.opponent_id.id
        if self.case_year:
            case_vals["case_year"] = self.case_year
        if self.case_number:
            if not self.case_number.isdigit():
                raise UserError(_("Court case number should contain digits only."))
            case_vals["case_number"] = int(self.case_number)
        if self.notes:
            description = case_vals.get("description") or ""
            case_vals["description"] = "%s\n%s" % (description, self.notes)

        case = self.env["qlk.case"].create(case_vals)
        if not project.case_id:
            project.case_id = case.id
        if project.pre_litigation_id and "pre_litigation_id" in case._fields:
            case.pre_litigation_id = project.pre_litigation_id.id
        action = self.env.ref("qlk_law.act_open_qlk_case_view", raise_if_not_found=False)
        if action:
            result = action.read()[0]
            result["res_id"] = case.id
            result["view_mode"] = "form"
            result["views"] = [(False, "form")]
            return result
        return {"type": "ir.actions.act_window_close"}
