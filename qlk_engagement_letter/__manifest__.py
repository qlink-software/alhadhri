# -*- coding: utf-8 -*-
{
    "name": "QLaw Engagement Letters",
    "summary": "Manage engagement letters for Al Hadhri Law Firm with dynamic contract controls.",
    "version": "1.0.0",
    "category": "Law",
    "license": "LGPL-3",
    "author": "Qlink Software",
    "website": "http://www.qlinksoftware.com",
    "depends": [
        "base",
        "mail",
        "contacts",
        "account",
        "qlk_law",
    ],
    "data": [
        "security/engagement_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/client_code_sequence.xml",
        "data/article_template.xml",
        "data/mail_template.xml",
        "data/cron_data.xml",
        "views/res_company_views.xml",
        "views/engagement_letter_views.xml",
        "views/engagement_letter_menu.xml",
        "report/engagement_letter_report.xml",
        "report/engagement_letter_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_engagement_letter/static/src/scss/engagement_letter.scss",
        ],
    },
    "installable": True,
    "application": False,
    "sequence": 25,
}
