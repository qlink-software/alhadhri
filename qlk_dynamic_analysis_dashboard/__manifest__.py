# -*- coding: utf-8 -*-
{
    "name": "QLK Dynamic Analysis Dashboard",
    "version": "18.0.1.0.0",
    "summary": "Responsive analytical dashboard with static charts for quick reporting.",
    "description": """
Deliver a ready-to-use analytical dashboard that highlights key legal KPIs
through static charts, responsive layouts, and curated insights for partners.
""",
    "author": "Codex",
    "website": "https://www.example.com",
    "category": "Services",
    "license": "OPL-1",
    "depends": [
        "base",
        "web",
        "qlk_law",
        "qlk_management",
        "qlk_task_management",
    ],
    "data": [
        "views/dynamic_analysis_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_dynamic_analysis_dashboard/static/src/scss/dynamic_analysis_dashboard.scss",
            "qlk_dynamic_analysis_dashboard/static/src/js/dynamic_analysis_dashboard.js",
            "qlk_dynamic_analysis_dashboard/static/src/xml/dynamic_analysis_dashboard.xml",
        ],
    },
    "installable": True,
    "application": True,
}
