# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# امتداد اتفاقية EL لربطها بالمشاريع وإنشاء مشروع جديد بعد الموافقة.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models


class BDEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    def _prepare_project_vals(self):
        vals = super()._prepare_project_vals()
        proj_type_map = {
            "litigation": "litigation",
            "corporate": "corporate",
            "both": "corporate",
        }
        proj_type = proj_type_map.get(self.retainer_type or "corporate", "corporate")
        department_map = {
            "litigation": "litigation",
            "corporate": "corporate",
            "arbitration": "arbitration",
        }
        default_department = department_map.get(proj_type, "litigation")
        vals.update(
            {
                "project_type": proj_type,
                "department": default_department,
                "litigation_stage": "court" if proj_type == "litigation" else False,
                "owner_id": self.reviewer_id.id or self.env.user.id,
                "reference": self.code,
                "project_scope": self.project_scope,
            }
        )
        primary_employee = self.lawyer_employee_id
        if not primary_employee and self.lawyer_id:
            primary_employee = self.env["hr.employee"].search(
                [("user_id.partner_id", "=", self.lawyer_id.id)], limit=1
            )
        if not primary_employee and self.reviewer_id:
            primary_employee = self.env["hr.employee"].search([("user_id", "=", self.reviewer_id.id)], limit=1)
        if primary_employee:
            vals["assigned_employee_ids"] = [(6, 0, [primary_employee.id])]
        return vals
