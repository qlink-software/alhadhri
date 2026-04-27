# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


class QlkSecuredCase(models.Model):
    _inherit = "qlk.case"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("employee_id.user_id", "employee_ids.user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            users = record.employee_ids.mapped("user_id")
            if record.employee_id.user_id:
                users |= record.employee_id.user_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkSecuredTask(models.Model):
    _inherit = "qlk.task"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("employee_id.user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            record.access_lawyer_ids = [Command.set(record.employee_id.user_id.ids)]


class QlkSecuredProjectTask(models.Model):
    _inherit = "project.task"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("user_ids")
    def _compute_access_lawyer_ids(self):
        for record in self:
            record.access_lawyer_ids = [Command.set(record.user_ids.ids)]


class QlkSecuredManagementTask(models.Model):
    _inherit = "task"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("user_id", "employee_ids.user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            users = record.employee_ids.mapped("user_id")
            if record.user_id:
                users |= record.user_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkSecuredLead(models.Model):
    _inherit = "crm.lead"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            record.access_lawyer_ids = [Command.set(record.user_id.ids)]


class QlkSecuredProposal(models.Model):
    _inherit = "bd.proposal"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("lawyer_user_id", "lawyer_ids.user_id", "reviewer_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            users = record.lawyer_ids.mapped("user_id")
            if record.lawyer_user_id:
                users |= record.lawyer_user_id
            if record.reviewer_id:
                users |= record.reviewer_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkSecuredEngagement(models.Model):
    _inherit = "bd.engagement.letter"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("lawyer_user_id", "lawyer_ids.user_id", "reviewer_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            users = record.lawyer_ids.mapped("user_id")
            if record.lawyer_user_id:
                users |= record.lawyer_user_id
            if record.reviewer_id:
                users |= record.reviewer_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkSecuredStandardProject(models.Model):
    _inherit = "project.project"

    access_lawyer_id = fields.Many2one(
        "res.users",
        string="Access Lawyer",
        compute="_compute_access_lawyer_ids",
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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("lawyer_id.user_id", "user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            users = record.lawyer_id.user_id
            if record.user_id:
                users |= record.user_id
            record.access_lawyer_id = record.lawyer_id.user_id or record.user_id
            record.access_lawyer_ids = [Command.set(users.ids)]


class QlkSecuredCorporateCase(models.Model):
    _inherit = "qlk.corporate.case"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("responsible_user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            record.access_lawyer_ids = [Command.set(record.responsible_user_id.ids)]


class QlkSecuredArbitrationCase(models.Model):
    _inherit = "qlk.arbitration.case"

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
        compute="_compute_access_lawyer_ids",
        store=True,
        compute_sudo=True,
    )

    @api.depends("responsible_user_id")
    def _compute_access_lawyer_ids(self):
        for record in self:
            record.access_lawyer_ids = [Command.set(record.responsible_user_id.ids)]
