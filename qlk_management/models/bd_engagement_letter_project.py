# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# امتداد اتفاقية EL لربطها بالمشاريع وإنشاء مشروع جديد بعد الموافقة.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models


class BDEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    def _prepare_project_vals(self):
        vals = super()._prepare_project_vals()
        retainer = self.retainer_type or "corporate"
        if "litigation" in retainer:
            proj_type = "litigation"
        elif "arbitration" in retainer and "corporate" not in retainer:
            proj_type = "arbitration"
        else:
            proj_type = "corporate"
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
                "scope_of_work": self.scope_of_work,
            }
        )
        employee_ids = self.lawyer_ids.ids if self.lawyer_ids else []
        primary_employee = self.lawyer_employee_id
        if not primary_employee and self.lawyer_id:
            primary_employee = self.env["hr.employee"].search(
                [("user_id.partner_id", "=", self.lawyer_id.id)], limit=1
            )
        if not primary_employee and self.reviewer_id:
            primary_employee = self.env["hr.employee"].search([("user_id", "=", self.reviewer_id.id)], limit=1)
        if not employee_ids and primary_employee:
            employee_ids = [primary_employee.id]
        if employee_ids:
            vals["assigned_employee_ids"] = [(6, 0, employee_ids)]
        return vals
