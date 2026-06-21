# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SubProject(models.Model):
    _name = "sub.project"
    _description = "Legal Sub Project"

    name = fields.Char('Name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    partner_id = fields.Many2one('res.partner', string='Client')
    client_file_id = fields.Many2one(
        "qlk.client.file",
        string="Client File",
        ondelete="restrict",
        index=True,
    )
    project_id = fields.Many2one(
        "qlk.project",
        string="Legal Project",
        ondelete="restrict",
        index=True,
        domain="[('client_file_id', '=', client_file_id)]",
    )
    description = fields.Html('description')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachments",
    )

    @api.onchange("client_file_id")
    def _onchange_client_file_id(self):
        for record in self:
            if record.client_file_id:
                record.partner_id = record.client_file_id.partner_id
            if record.project_id and record.project_id.client_file_id != record.client_file_id:
                record.project_id = False

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for record in self:
            if record.project_id:
                record.client_file_id = record.project_id.client_file_id
                record.partner_id = record.project_id.client_id

    @api.constrains("project_id", "client_file_id")
    def _check_project_client_file(self):
        for record in self:
            if (
                record.project_id
                and record.client_file_id
                and record.project_id.client_file_id != record.client_file_id
            ):
                raise ValidationError(
                    _("The legal project must belong to the selected client file.")
                )
