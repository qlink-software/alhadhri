# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


class ProjectTask(models.Model):
    _inherit = "project.task"

    case_id = fields.Many2one(
        "qlk.case",
        string="Litigation Case",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    qlk_project_id = fields.Many2one(
        "qlk.project",
        string="Legal Project",
        related="case_id.project_id",
        store=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Primary Assignee",
        compute="_compute_primary_user_id",
        inverse="_inverse_primary_user_id",
        store=True,
        index=True,
        help="Stored primary assignee used by strict lawyer record rules.",
    )

    @api.depends("user_ids")
    def _compute_primary_user_id(self):
        # Odoo 18 uses user_ids; this alias keeps security domains simple and indexed.
        for task in self:
            task.user_id = task.user_ids[:1] if task.user_ids else False

    def _inverse_primary_user_id(self):
        for task in self:
            task.user_ids = [Command.set([task.user_id.id])] if task.user_id else [Command.clear()]

    @api.onchange("case_id")
    def _onchange_case_id(self):
        for task in self:
            case = task.case_id
            if case and case.client_id and not task.partner_id:
                task.partner_id = case.client_id.id
            if case and case.project_id and case.project_id.timesheet_project_id and not task.project_id:
                task.project_id = case.project_id.timesheet_project_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_legal_case_defaults(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("case_id") and not vals.get("project_id"):
            self._apply_legal_case_defaults(vals)
        return super().write(vals)

    def _apply_legal_case_defaults(self, vals):
        case_id = vals.get("case_id")
        if not case_id:
            return vals
        case = self.env["qlk.case"].browse(case_id)
        if not case.exists():
            return vals
        if case.client_id and not vals.get("partner_id"):
            vals["partner_id"] = case.client_id.id
        legal_project = case.project_id
        if legal_project and not vals.get("project_id"):
            vals["project_id"] = legal_project._get_or_create_timesheet_project().id
        return vals

    @api.constrains("case_id")
    def _check_case_required_for_legal_task(self):
        if not self.env.context.get("qlk_require_case_id"):
            return
        for task in self:
            if not task.case_id:
                raise ValidationError(_("Tasks created from legal cases must be linked to a case."))
