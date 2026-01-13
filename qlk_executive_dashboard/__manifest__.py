# -*- coding: utf-8 -*-
{
    "name": "QLK Executive Dashboard",
    "version": "18.0.1.0.0",
    "summary": "Executive management dashboard for legal, finance, HR, and approvals.",
    "description": "Read-only executive dashboard providing KPI-driven insights for management.",
    "author": "Qlink Software",
    "website": "http://www.qlinksoftware.com",
    "category": "QLK - Management",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "account",
        "hr",
        "hr_holidays",
        "qlk_management",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/executive_dashboard_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_executive_dashboard/static/src/js/executive_dashboard.js",
            "qlk_executive_dashboard/static/src/xml/executive_dashboard.xml",
            "qlk_executive_dashboard/static/src/scss/executive_dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}
