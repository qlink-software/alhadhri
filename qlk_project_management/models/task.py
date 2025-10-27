# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QlkTask(models.Model):
    _inherit = "qlk.task"

    department = fields.Selection(
        selection_add=[
            ("pre_litigation", "Pre-Litigation"),
            ("arbitration", "Arbitration"),
        ],
        ondelete={
            "pre_litigation": "set default",
            "arbitration": "set default",
        },
    )
    project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        tracking=True,
        ondelete="set null",
    )

    @api.depends("employee_id", "project_id.company_id")
    def _compute_company_ids(self):
        super()._compute_company_ids()
        for task in self:
            if task.project_id and task.project_id.company_id:
                task.company_ids |= task.project_id.company_id

    @api.onchange("department")
    def _onchange_department(self):
        super()._onchange_department()
        if self.department not in ("litigation", "pre_litigation"):
            self.litigation_phase = False
            self.case_id = False
        if self.department != "corporate":
            self.engagement_id = False
        if self.department not in {"litigation", "pre_litigation", "corporate", "arbitration"}:
            self.project_id = False

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if not self.project_id:
            return
        project = self.project_id
        self.company_id = project.company_id.id
        if project.assigned_employee_ids:
            self.employee_id = project.assigned_employee_ids[:1].id

        if project.department == "corporate":
            self.department = "corporate"
            self.engagement_id = project.engagement_id.id
            self.case_id = False
            self.litigation_phase = False
        elif project.department == "litigation":
            self.department = "litigation"
            self.case_id = project.case_id.id
            self.litigation_phase = self.litigation_phase or "post"
            self.engagement_id = project.engagement_id.id
        elif project.department == "pre_litigation":
            self.department = "pre_litigation"
            self.case_id = False
            self.litigation_phase = False
            self.engagement_id = project.engagement_id.id
        else:  # arbitration / management alike
            self.department = "arbitration"
            self.case_id = False
            self.litigation_phase = False
            self.engagement_id = project.engagement_id.id

    @api.constrains("department", "case_id", "engagement_id", "litigation_phase", "project_id")
    def _check_department_links(self):
        for task in self:
            if task.department == "litigation":
                if not task.case_id and not task.project_id:
                    raise ValidationError(_("Litigation tasks must be linked to a litigation case or litigation project."))
                if task.case_id and not task.litigation_phase:
                    raise ValidationError(_("Specify whether the litigation task is pre or post litigation."))
            elif task.department == "pre_litigation":
                if not task.project_id:
                    raise ValidationError(_("Pre-Litigation tasks must be linked to a project."))
                if task.case_id:
                    raise ValidationError(_("Pre-Litigation tasks cannot be linked to a court case."))
            elif task.department == "corporate":
                if not task.project_id and not task.engagement_id:
                    raise ValidationError(_("Corporate tasks must be linked to a corporate project or engagement letter."))
            elif task.department == "arbitration":
                if not task.project_id:
                    raise ValidationError(_("Arbitration tasks must be linked to a project."))
            elif task.department == "management" and task.case_id:
                raise ValidationError(_("Management tasks cannot be linked to a litigation case."))
