# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectLogHours(models.TransientModel):
    _name = "qlk.project.log.hours"
    _description = "Quick Project Hours Entry"

    project_id = fields.Many2one("qlk.project", required=True, ondelete="cascade")
    task_name = fields.Char(string="Task", required=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        default=lambda self: self.env.user.employee_id,
    )
    hours_spent = fields.Float(string="Hours", required=True, digits="Product Unit of Measure")
    date_start = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    description = fields.Text(string="Notes")
    department = fields.Selection(
        selection=[
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("management", "Management"),
        ],
        string="Department",
        required=True,
        default=lambda self: self._default_department(),
    )
    litigation_phase = fields.Selection(
        selection=[
            ("pre", "Pre-Litigation"),
            ("post", "Post-Litigation"),
        ],
        string="Litigation Phase",
    )

    def _default_department(self):
        project = self.env.context.get("default_project_id")
        if project:
            record = self.env["qlk.project"].browse(project)
            if record.exists():
                return record.department
        return "litigation"

    @api.onchange("department")
    def _onchange_department(self):
        if self.department != "litigation":
            self.litigation_phase = False

    def action_log_hours(self):
        self.ensure_one()
        if self.hours_spent <= 0:
            raise UserError(_("Hours must be greater than zero."))
        project = self.project_id
        values = {
            "name": self.task_name,
            "project_id": project.id,
            "department": self.department or project.department,
            "employee_id": self.employee_id.id,
            "hours_spent": self.hours_spent,
            "date_start": self.date_start,
            "description": self.description,
            "approval_state": "draft",
        }
        if values["department"] == "litigation":
            if not project.case_id:
                raise UserError(_("Link the project to a litigation case before logging litigation hours."))
            values.update(
                {
                    "case_id": project.case_id.id,
                    "litigation_phase": self.litigation_phase or "pre",
                }
            )
        elif values["department"] == "corporate":
            if not project.engagement_id:
                raise UserError(_("Corporate hours require an engagement letter linked to the project."))
            values["engagement_id"] = project.engagement_id.id
        task = self.env["qlk.task"].create(values)
        project.message_post(
            body=_("Logged %(hours)s hours to task %(task)s.", hours=self.hours_spent, task=task.display_name)
        )
        return {"type": "ir.actions.act_window_close"}
