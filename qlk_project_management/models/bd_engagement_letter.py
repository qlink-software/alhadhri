# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# امتداد اتفاقية EL لربطها بالمشاريع وإنشاء مشروع جديد بعد الموافقة.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BDEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    project_id = fields.Many2one("qlk.project", string="Project", readonly=True, copy=False)

    def action_create_project(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only approved engagement letters can create projects."))
        if not self.partner_id:
            raise UserError(_("Please select a client before creating the project."))

        project = self.project_id
        if not project:
            project_type_map = {
                "litigation": "litigation",
                "corporate": "corporate",
                "both": "corporate",
            }
            proj_type = project_type_map.get(self.retainer_type or "corporate", "corporate")
            department_map = {
                "litigation": "litigation",
                "corporate": "corporate",
                "arbitration": "arbitration",
            }
            default_department = department_map.get(proj_type, "litigation")
            employee_ids = None
            primary_employee = self.lawyer_id
            if not primary_employee and self.reviewer_id:
                primary_employee = self.env["hr.employee"].search([("user_id", "=", self.reviewer_id.id)], limit=1)
            if primary_employee:
                employee_ids = [(6, 0, [primary_employee.id])]
            project_vals = {
                "name": self.name or _("New Project"),
                "client_id": self.partner_id.id,
                "project_type": proj_type,
                "department": default_department,
                "litigation_stage": "court" if proj_type == "litigation" else False,
                "company_id": self.company_id.id if self.company_id else self.env.company.id,
                "owner_id": self.reviewer_id.id or self.env.user.id,
                "reference": self.reference_number,
                "description": self.services_description,
                "project_scope": self.project_scope,
            }
            if employee_ids:
                project_vals["assigned_employee_ids"] = employee_ids
            project = self.env["qlk.project"].create(project_vals)
            self.project_id = project.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project",
            "res_id": project.id,
            "view_mode": "form",
            "target": "current",
        }
