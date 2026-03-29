# -*- coding: utf-8 -*-
from odoo import api, models


class BdPdfBuilderLegacyCleanup(models.AbstractModel):
    _name = "bd.pdf.builder.legacy.cleanup"
    _description = "BD PDF Builder Legacy Cleanup"

    @api.model
    def cleanup_legacy_records(self):
        legacy_xmlids = [
            "bd_pdf_builder.action_proposal_pdf",
            "bd_pdf_builder.report_proposal_pdf",
            "bd_pdf_builder.proposal_template_modern",
            "bd_pdf_builder.bd_pdf_template_proposal_modern",
            "bd_pdf_builder.bd_pdf_template_engagement_classic",
            "bd_pdf_builder.view_bd_proposal_form_pdf_builder",
            "bd_pdf_builder.view_bd_pdf_builder_res_config_settings",
            "bd_pdf_builder.view_bd_pdf_builder_wizard",
        ]

        imd_model = self.env["ir.model.data"].sudo()
        for xmlid in legacy_xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                record.sudo().unlink()

            module, name = xmlid.split(".", 1)
            imd_model.search([
                ("module", "=", module),
                ("name", "=", name),
            ]).unlink()

        return True
