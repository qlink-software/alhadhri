# -*- coding: utf-8 -*-
from odoo import fields, models


class QlkPoliceComplaint(models.Model):
    _inherit = "qlk.police.complaint"

    project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    client_file_id = fields.Many2one(
        "qlk.client.file",
        string="Client File",
        related="project_id.client_file_id",
        store=True,
        readonly=True,
        index=True,
    )
    engagement_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        related="project_id.engagement_letter_id",
        store=True,
        readonly=True,
        index=True,
    )
