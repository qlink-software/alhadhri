# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

from .proposal_pdf_builder import PDF_LAYOUT_SELECTION


class BdEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    engagement_pdf_template_id = fields.Many2one(
        "bd.pdf.builder.template",
        string="Engagement PDF Template",
        domain="[('model', '=', 'bd.engagement.letter')]",
    )
    engagement_pdf_layout = fields.Selection(selection=PDF_LAYOUT_SELECTION, string="PDF Layout")
    engagement_pdf_header_html = fields.Html(string="PDF Header", sanitize=True)
    engagement_pdf_footer_html = fields.Html(string="PDF Footer", sanitize=True)

    def _get_default_engagement_template(self):
        company = self.env.company
        template = (
            self.engagement_pdf_template_id
            or company.bd_engagement_template_id
            or self.env["bd.pdf.builder.template"].search(
                [("model", "=", "bd.engagement.letter")], limit=1
            )
        )
        if not template:
            raise UserError(_("Please configure at least one Engagement Letter template."))
        return template

    def _build_engagement_pdf_context(self, template):
        header = self.engagement_pdf_header_html or template.default_header_html or ""
        footer = self.engagement_pdf_footer_html or template.default_footer_html or ""
        layout = self.engagement_pdf_layout or template.default_layout or "classic"
        return {
            "builder_template": template.template_key,
            "builder_layout": layout,
            "builder_header_html": header,
            "builder_footer_html": footer,
        }

    def action_print_engagement_pdf(self):
        self.ensure_one()
        action = self.env.ref("bd_pdf_builder.action_engagement_letter_pdf")
        template = self._get_default_engagement_template()
        ctx = self._build_engagement_pdf_context(template)
        return action.with_context(**ctx).report_action(self)

    def _prepare_pdf_builder_wizard_context(self, template):
        layout = self.engagement_pdf_layout or template.default_layout or "classic"
        header = self.engagement_pdf_header_html or template.default_header_html
        footer = self.engagement_pdf_footer_html or template.default_footer_html
        return {
            "default_res_model": "bd.engagement.letter",
            "default_res_id": self.id,
            "default_template_id": template.id,
            "default_layout": layout,
            "default_header_html": header,
            "default_footer_html": footer,
        }

    def action_customize_engagement_pdf(self):
        self.ensure_one()
        template = self._get_default_engagement_template()
        context = self._prepare_pdf_builder_wizard_context(template)
        return {
            "name": _("Customize Engagement PDF"),
            "type": "ir.actions.act_window",
            "res_model": "bd.pdf.builder.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
