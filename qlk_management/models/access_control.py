# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


def _department_code_from_service(value, default="litigation"):
    """Normalize workflow/service values into configured legal department codes."""
    if value in {"litigation", "corporate", "arbitration", "mp"}:
        return value
    if value in {"management", "management_litigation", "management_corporate"}:
        return "mp"
    if value == "litigation_corporate":
        return "litigation"
    return default


def _department_by_code(env, codes):
    return env["qlk.department"].sudo()._get_by_codes(codes)


class QlkDepartmentSecuredProject(models.Model):
    _inherit = "qlk.project"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "qlk_project_access_lawyer_rel",
        "project_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("department", "assigned_lawyer_id", "assigned_employee_ids.user_id", "lawyer_ids.user_id")
    def _compute_department_security_fields(self):
        departments = _department_by_code(self.env, [record.department for record in self] + ["litigation"])
        for record in self:
            users = record.assigned_employee_ids.mapped("user_id") | record.lawyer_ids.mapped("user_id")
            if record.assigned_lawyer_id:
                users |= record.assigned_lawyer_id
            record.department_id = departments.get(record.department) or departments.get("litigation")
            record.access_lawyer_id = record.assigned_lawyer_id or users[:1]
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredCase(models.Model):
    _inherit = "qlk.case"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="employee_id.user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "qlk_case_access_lawyer_rel",
        "case_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("project_id.department_id", "employee_id.user_id", "employee_ids.user_id")
    def _compute_department_security_fields(self):
        litigation = self.env["qlk.department"].sudo()._get_by_code("litigation")
        for record in self:
            users = record.employee_ids.mapped("user_id")
            if record.employee_id.user_id:
                users |= record.employee_id.user_id
            record.department_id = record.project_id.department_id or litigation
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredTask(models.Model):
    _inherit = "qlk.task"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="assigned_user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "qlk_task_access_lawyer_rel",
        "task_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("department", "project_id.department_id", "case_id.department_id", "employee_id.user_id")
    def _compute_department_security_fields(self):
        codes = [_department_code_from_service(record.department, default="mp") for record in self]
        departments = _department_by_code(self.env, codes + ["mp", "litigation"])
        for record in self:
            users = record.employee_id.user_id
            record.department_id = (
                record.project_id.department_id
                or record.case_id.department_id
                or departments.get(_department_code_from_service(record.department, default="mp"))
                or departments.get("mp")
            )
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredProjectTask(models.Model):
    _inherit = "project.task"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "project_task_access_lawyer_rel",
        "task_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("project_id.department_id", "user_id", "user_ids")
    def _compute_department_security_fields(self):
        mp_department = self.env["qlk.department"].sudo()._get_by_code("mp")
        for record in self:
            record.department_id = record.project_id.department_id or mp_department
            record.access_lawyer_ids = [Command.set(record.user_ids.ids)]


class QlkDepartmentSecuredManagementTask(models.Model):
    _inherit = "task"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access User",
        related="user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "management_task_access_user_rel",
        "task_id",
        "user_id",
        string="Access Users",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("proposal_id.department_id", "crm_id.department_id", "user_id", "employee_ids.user_id")
    def _compute_department_security_fields(self):
        mp_department = self.env["qlk.department"].sudo()._get_by_code("mp")
        for record in self:
            users = record.employee_ids.mapped("user_id")
            if record.user_id:
                users |= record.user_id
            record.department_id = record.proposal_id.department_id or record.crm_id.department_id or mp_department
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredLead(models.Model):
    _inherit = "crm.lead"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access User",
        related="user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "crm_lead_access_user_rel",
        "lead_id",
        "user_id",
        string="Access Users",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("opportunity_type", "contract_type", "user_id")
    def _compute_department_security_fields(self):
        codes = [_department_code_from_service(record.opportunity_type or record.contract_type) for record in self]
        departments = _department_by_code(self.env, codes + ["litigation"])
        for record in self:
            code = _department_code_from_service(record.opportunity_type or record.contract_type)
            record.department_id = departments.get(code) or departments.get("litigation")
            record.access_lawyer_ids = [Command.set(record.user_id.ids)]


class QlkDepartmentSecuredProposal(models.Model):
    _inherit = "bd.proposal"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="lawyer_user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "bd_proposal_access_lawyer_rel",
        "proposal_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("retainer_type", "lawyer_user_id", "lawyer_ids.user_id", "reviewer_id")
    def _compute_department_security_fields(self):
        codes = [_department_code_from_service(record.retainer_type) for record in self]
        departments = _department_by_code(self.env, codes + ["litigation"])
        for record in self:
            users = record.lawyer_ids.mapped("user_id")
            if record.lawyer_user_id:
                users |= record.lawyer_user_id
            if record.reviewer_id:
                users |= record.reviewer_id
            record.department_id = departments.get(_department_code_from_service(record.retainer_type)) or departments.get("litigation")
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredEngagement(models.Model):
    _inherit = "bd.engagement.letter"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="lawyer_user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "bd_engagement_access_lawyer_rel",
        "letter_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("retainer_type", "lawyer_user_id", "lawyer_ids.user_id", "reviewer_id")
    def _compute_department_security_fields(self):
        codes = [_department_code_from_service(record.retainer_type) for record in self]
        departments = _department_by_code(self.env, codes + ["litigation"])
        for record in self:
            users = record.lawyer_ids.mapped("user_id")
            if record.lawyer_user_id:
                users |= record.lawyer_user_id
            if record.reviewer_id:
                users |= record.reviewer_id
            record.department_id = departments.get(_department_code_from_service(record.retainer_type)) or departments.get("litigation")
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredStandardProject(models.Model):
    _inherit = "project.project"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "project_project_access_lawyer_rel",
        "project_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("project_type", "retainer_type", "contract_type", "lawyer_id.user_id", "user_id")
    def _compute_department_security_fields(self):
        codes = [
            _department_code_from_service(record.contract_type or record.retainer_type or record.project_type, default="corporate")
            for record in self
        ]
        departments = _department_by_code(self.env, codes + ["corporate"])
        for record in self:
            users = record.lawyer_id.user_id
            if record.user_id:
                users |= record.user_id
            code = _department_code_from_service(
                record.contract_type or record.retainer_type or record.project_type,
                default="corporate",
            )
            record.department_id = departments.get(code) or departments.get("corporate")
            record.access_lawyer_id = record.lawyer_id.user_id or record.user_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkDepartmentSecuredCorporateCase(models.Model):
    _inherit = "qlk.corporate.case"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="responsible_user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "corporate_case_access_lawyer_rel",
        "case_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("responsible_user_id")
    def _compute_department_security_fields(self):
        corporate = self.env["qlk.department"].sudo()._get_by_code("corporate")
        for record in self:
            record.department_id = corporate
            record.access_lawyer_ids = [Command.set(record.responsible_user_id.ids)]


class QlkDepartmentSecuredArbitrationCase(models.Model):
    _inherit = "qlk.arbitration.case"

    department_id = fields.Many2one(
        "qlk.department",
        string="Access Department",
        compute="_compute_department_security_fields",
        store=True,
        index=True,
        compute_sudo=True,
    )
    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        related="responsible_user_id",
        store=True,
        index=True,
        readonly=True,
    )
    access_lawyer_ids = fields.Many2many(
        "res.users",
        "arbitration_case_access_lawyer_rel",
        "case_id",
        "user_id",
        string="Access Lawyers",
        compute="_compute_department_security_fields",
        store=True,
        compute_sudo=True,
    )

    @api.depends("responsible_user_id")
    def _compute_department_security_fields(self):
        arbitration = self.env["qlk.department"].sudo()._get_by_code("arbitration")
        for record in self:
            record.department_id = arbitration
            record.access_lawyer_ids = [Command.set(record.responsible_user_id.ids)]
