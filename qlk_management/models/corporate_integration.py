# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CorporateCaseProject(models.Model):
    _inherit = "qlk.corporate.case"

    engagement_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    service_code = fields.Char(string="Service Code", readonly=True, copy=False)
    agreement_hours = fields.Float(string="Agreement Hours", tracking=True)
    agreement_start_date = fields.Date(string="Agreement Start Date", tracking=True)
    agreement_end_date = fields.Date(string="Agreement End Date", tracking=True)
    actual_hours_total = fields.Float(string="Approved Hours", compute="_compute_project_hours", store=False)
    actual_hours_month = fields.Float(string="Approved Hours (Month)", compute="_compute_project_hours", store=False)
    over_hours = fields.Boolean(string="Over Agreement Hours", compute="_compute_project_hours", store=False)
    client_capacity = fields.Char(string="Client Capacity/Title")
    # client_document_ids = fields.One2many(
    #     related="client_id.client_document_ids",
    #     string="Client Documents",
    #     readonly=True,
    # )

    @api.depends("engagement_id", "agreement_hours")
    def _compute_project_hours(self):
        Task = self.env["qlk.task"]
        approved_states = {"approved"}
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for record in self:
            record.actual_hours_total = 0.0
            record.actual_hours_month = 0.0
            record.over_hours = False
            domain = []
            if not record.engagement_id:
                continue
            domain = [("engagement_id", "=", record.engagement_id.id)]
            domain.append(("approval_state", "in", list(approved_states)))
            tasks = Task.search(domain)
            total = sum(tasks.mapped("hours_spent"))
            month_hours = sum(
                task.hours_spent
                for task in tasks
                if task.date_start and task.date_start >= month_start
            )
            record.actual_hours_total = total
            record.actual_hours_month = month_hours
            if record.agreement_hours:
                record.over_hours = total > record.agreement_hours

    def action_open_project_hours(self):
        self.ensure_one()
        if not self.engagement_id:
            return False
        domain = [("engagement_id", "=", self.engagement_id.id)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Hours"),
            "res_model": "qlk.task",
            "view_mode": "list,form",
            "domain": domain,
        }

    @api.onchange("engagement_id")
    def _onchange_engagement_id(self):
        for record in self:
            engagement = record.engagement_id
            if not engagement:
                continue
            if engagement.partner_id and not record.client_id:
                record.client_id = engagement.partner_id.id
            if engagement.lawyer_employee_id and not record.responsible_employee_id:
                record.responsible_employee_id = engagement.lawyer_employee_id.id

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for record in self:
            project = record.project_id
            if not project:
                continue
            if project.engagement_letter_id and not record.engagement_id:
                record.engagement_id = project.engagement_letter_id.id
            if project.client_id and not record.client_id:
                record.client_id = project.client_id.id
            if project.lawyer_id and not record.responsible_employee_id:
                record.responsible_employee_id = project.lawyer_id.id
            service_code = getattr(project, "service_code", False)
            if service_code and not record.service_code:
                record.service_code = service_code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Corporate records must be created from a project."))
            if vals.get("project_id"):
                self._ensure_project_manager()
            self._apply_project_defaults(vals)
        if not self.env.context.get("skip_engagement_service_validation"):
            for vals in vals_list:
                engagement = self.env["bd.engagement.letter"].browse(vals.get("engagement_id"))
                if engagement and not engagement._service_allows("corporate"):
                    raise UserError(_("This engagement letter does not allow corporate records."))
        return super().create(vals_list)

    def write(self, vals):
        if "project_id" in vals:
            if not vals.get("project_id"):
                raise ValidationError(_("Corporate records must be linked to a project."))
            if vals.get("project_id"):
                self._ensure_project_manager()
                self._apply_project_defaults(vals)
        if vals.get("engagement_id") and not self.env.context.get("skip_engagement_service_validation"):
            engagement = self.env["bd.engagement.letter"].browse(vals["engagement_id"])
            if engagement and not engagement._service_allows("corporate"):
                raise UserError(_("This engagement letter does not allow corporate records."))
        return super().write(vals)

    def _apply_project_defaults(self, vals):
        project_id = vals.get("project_id")
        if not project_id:
            return vals
        project = self.env[self._fields["project_id"].comodel_name].browse(project_id)
        if project.exists():
            vals.setdefault("client_file_id", project.client_file_id.id if "client_file_id" in project._fields else False)
            vals.setdefault("engagement_id", project.engagement_letter_id.id)
            vals.setdefault("client_id", project.client_id.id)
            vals.setdefault("service_code", getattr(project, "service_code", False))
            vals.setdefault("responsible_employee_id", project.lawyer_id.id)
        return vals

    def _ensure_project_manager(self):
        project_model = self.env[self._fields["project_id"].comodel_name]
        if hasattr(project_model, "_ensure_legal_manager"):
            return project_model._ensure_legal_manager()
        return True

    @api.constrains("project_id")
    def _check_project_service_rules(self):
        for record in self:
            if not record.project_id:
                raise ValidationError(_("Corporate records must be created from a project."))
            allowed = (
                record.project_id._allows_legal_service("corporate")
                if hasattr(record.project_id, "_allows_legal_service")
                else record.project_id.service_type == "corporate"
            )
            if not allowed:
                raise ValidationError(_("This project does not allow corporate records."))
            duplicate = self.search_count([
                ("project_id", "=", record.project_id.id),
                ("id", "!=", record.id),
            ])
            if duplicate:
                raise ValidationError(_("A corporate record already exists for this project."))
