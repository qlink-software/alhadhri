# -*- coding: utf-8 -*-
{
    "name": "BD PDF Builder",
    "version": "18.0.1.0.0",
    "summary": "Custom PDF builder for BD proposals and engagement letters",
    "depends": [
        "web",
        "qlk_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/pdf_builder_templates.xml",
        "views/templates/proposal_pdf_templates.xml",
        "views/templates/engagement_letter_pdf_templates.xml",
        "report/proposal_pdf_report.xml",
        "report/engagement_letter_pdf_report.xml",
        "views/bd_proposal_views.xml",
        "views/bd_engagement_letter_views.xml",
        "views/bd_pdf_builder_settings.xml",
        "wizard/bd_pdf_builder_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bd_pdf_builder/static/src/scss/pdf_builder.scss",
            "bd_pdf_builder/static/src/js/pdf_builder.js",
        ],
    },
    "license": "LGPL-3",
}
