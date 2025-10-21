# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    engagement_license_number = fields.Char(string="Engagement License Number")
    engagement_office_location = fields.Char(string="Engagement Office Location")
    engagement_office_email = fields.Char(string="Engagement Office Email")
    engagement_office_phone = fields.Char(string="Engagement Office Phone")
    engagement_authorized_signatory_name = fields.Char(string="Engagement Authorized Signatory")
    engagement_authorized_signatory_title = fields.Char(string="Authorized Signatory Title")
    engagement_authorized_signatory_details = fields.Text(string="Authorized Signatory Details")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    engagement_license_number = fields.Char(
        related="company_id.engagement_license_number",
        readonly=False,
    )
    engagement_office_location = fields.Char(
        related="company_id.engagement_office_location",
        readonly=False,
    )
    engagement_office_email = fields.Char(
        related="company_id.engagement_office_email",
        readonly=False,
    )
    engagement_office_phone = fields.Char(
        related="company_id.engagement_office_phone",
        readonly=False,
    )
    engagement_authorized_signatory_name = fields.Char(
        related="company_id.engagement_authorized_signatory_name",
        readonly=False,
    )
    engagement_authorized_signatory_title = fields.Char(
        related="company_id.engagement_authorized_signatory_title",
        readonly=False,
    )
    engagement_authorized_signatory_details = fields.Text(
        related="company_id.engagement_authorized_signatory_details",
        readonly=False,
    )

    def set_values(self):
        # Ensure standard super call is kept for correct behavior
        super().set_values()

