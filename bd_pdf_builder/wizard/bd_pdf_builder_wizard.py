# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.proposal_pdf_builder import PDF_LAYOUT_SELECTION


class BdPdfBuilderWizard(models.TransientModel):
    _name = "bd.pdf.builder.wizard"
    _description = "BD PDF Builder Wizard"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    template_id = fields.Many2one(
        "bd.pdf.builder.template",
        string="Template",
        required=True,
    )
    layout = fields.Selection(selection=PDF_LAYOUT_SELECTION, required=True, default="modern")
    header_html = fields.Html(string="Header", sanitize=True)
    footer_html = fields.Html(string="Footer", sanitize=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        template = defaults.get("template_id")
        if template:
            template = self.env["bd.pdf.builder.template"].browse(template)
            defaults.setdefault("layout", template.default_layout or "modern")
            defaults.setdefault("header_html", template.default_header_html)
            defaults.setdefault("footer_html", template.default_footer_html)
        return defaults

    def _get_target_record(self):
        if not self.res_model or not self.res_id:
            raise UserError(_("The wizard is missing a target record."))
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_("The target record was not found or has been deleted."))
        return record

    def action_generate_pdf(self):
        self.ensure_one()
        record = self._get_target_record()
        if self.res_model == "bd.proposal":
            record.write(
                {
                    "proposal_pdf_template_id": self.template_id.id,
                    "proposal_pdf_layout": self.layout,
                    "proposal_pdf_header_html": self.header_html,
                    "proposal_pdf_footer_html": self.footer_html,
                }
            )
            action = record.action_print_proposal_pdf()
        elif self.res_model == "bd.engagement.letter":
            record.write(
                {
                    "engagement_pdf_template_id": self.template_id.id,
                    "engagement_pdf_layout": self.layout,
                    "engagement_pdf_header_html": self.header_html,
                    "engagement_pdf_footer_html": self.footer_html,
                }
            )
            action = record.action_print_engagement_pdf()
        else:
            raise UserError(_("Unsupported model for PDF builder."))
        return action
