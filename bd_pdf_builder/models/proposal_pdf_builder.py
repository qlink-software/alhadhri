# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

PDF_LAYOUT_SELECTION = [
    ("modern", "Modern"),
    ("classic", "Classic"),
    ("minimal", "Minimal"),
]


class BdPdfBuilderTemplate(models.Model):
    _name = "bd.pdf.builder.template"
    _description = "BD PDF Builder Template"

    name = fields.Char(required=True, translate=True)
    model = fields.Selection(
        selection=[
            ("bd.proposal", "Business Proposal"),
            ("bd.engagement.letter", "Engagement Letter"),
        ],
        required=True,
    )
    template_key = fields.Char(
        string="QWeb Template Key",
        required=True,
        help="Technical XML-ID of the QWeb template to render.",
    )
    default_layout = fields.Selection(selection=PDF_LAYOUT_SELECTION, default="modern")
    default_header_html = fields.Html(string="Default Header", sanitize=True)
    default_footer_html = fields.Html(string="Default Footer", sanitize=True)
    active = fields.Boolean(default=True)


class BdProposal(models.Model):
    _inherit = "bd.proposal"

    proposal_pdf_template_id = fields.Many2one(
        "bd.pdf.builder.template",
        string="Proposal PDF Template",
        domain="[('model', '=', 'bd.proposal')]",
    )
    proposal_pdf_layout = fields.Selection(
        selection=PDF_LAYOUT_SELECTION,
        string="PDF Layout",
    )
    proposal_pdf_header_html = fields.Html(string="PDF Header", sanitize=True)
    proposal_pdf_footer_html = fields.Html(string="PDF Footer", sanitize=True)

    def _get_default_proposal_template(self):
        company = self.env.company
        template = (
            self.proposal_pdf_template_id
            or company.bd_proposal_template_id
            or self.env["bd.pdf.builder.template"].search(
                [("model", "=", "bd.proposal")], limit=1
            )
        )
        if not template:
            raise UserError(_("Please configure at least one Proposal PDF template."))
        return template

    def _build_proposal_pdf_context(self, template):
        header = self.proposal_pdf_header_html or template.default_header_html or ""
        footer = self.proposal_pdf_footer_html or template.default_footer_html or ""
        layout = self.proposal_pdf_layout or template.default_layout or "modern"
        return {
            "builder_template": template.template_key,
            "builder_layout": layout,
            "builder_header_html": header,
            "builder_footer_html": footer,
        }

    def action_print_proposal_pdf(self):
        self.ensure_one()
        action = self.env.ref("bd_pdf_builder.action_proposal_pdf")
        template = self._get_default_proposal_template()
        ctx = self._build_proposal_pdf_context(template)
        return action.with_context(**ctx).report_action(self)

    def _prepare_pdf_builder_wizard_context(self, template):
        layout = self.proposal_pdf_layout or template.default_layout or "modern"
        header = self.proposal_pdf_header_html or template.default_header_html
        footer = self.proposal_pdf_footer_html or template.default_footer_html
        return {
            "default_res_model": "bd.proposal",
            "default_res_id": self.id,
            "default_template_id": template.id,
            "default_layout": layout,
            "default_header_html": header,
            "default_footer_html": footer,
        }

    def action_customize_proposal_pdf(self):
        self.ensure_one()
        template = self._get_default_proposal_template()
        context = self._prepare_pdf_builder_wizard_context(template)
        return {
            "name": _("Customize Proposal PDF"),
            "type": "ir.actions.act_window",
            "res_model": "bd.pdf.builder.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
