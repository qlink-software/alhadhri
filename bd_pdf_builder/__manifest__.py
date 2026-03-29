# -*- coding: utf-8 -*-
{
    "name": "BD Engagement Letter PDF",
    "version": "18.0.2.0.0",
    "summary": "Engagement Letter PDF report for BD module",
    "depends": [
        "web",
        "qlk_management",
    ],
    "data": [
        "data/legacy_cleanup.xml",
        "views/templates/engagement_letter_pdf_templates.xml",
        "report/engagement_letter_pdf_report.xml",
        "views/bd_engagement_letter_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "bd_pdf_builder/static/src/scss/pdf_builder.scss",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
