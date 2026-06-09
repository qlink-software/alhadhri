# -*- coding: utf-8 -*-
{
    "name": "BD Engagement Letter PDF",
    "version": "18.0.2.0.0",
    "summary": "Engagement Letter PDF report for BD module",
    "depends": [
        "web",
        "hr_recruitment",
        "qlk_management",
    ],
    "data": [
        "data/legacy_cleanup.xml",
        "views/templates/report_layout_standard.xml",
        "views/templates/proposal_pdf_templates.xml",
        "report/bd_standard_paperformat.xml",
        "report/proposal_pdf_report.xml",
        "views/templates/engagement_letter_pdf_templates.xml",
        "report/engagement_letter_pdf_report.xml",
        "report/service_agreement_pdf_reports.xml",
        "report/hr_applicant_pdf_reports.xml",
        "views/bd_proposal_views.xml",
        "views/bd_engagement_letter_views.xml",
        "views/hr_applicant_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "bd_pdf_builder/static/src/scss/bd_pdf_builder.scss",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
