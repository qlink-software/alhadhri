# -*- coding: utf-8 -*-
{
    "name": "QLK Approval Dashboard",
    "version": "18.0.1.0.0",
    "summary": "Interactive approval dashboard with dynamic sections and secure actions.",
    "description": """
Interactive approval dashboard for approval workflows across installed QLK modules.
The dashboard discovers readable approval models, applies record rules, aggregates
hours, and lets authorized users approve or reject records from a single OWL view.
""",
    "author": "Qlink Software",
    "website": "http://www.qlinksoftware.com",
    "category": "QLK - Management",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "qlk_security_base",
        "qlk_management",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_approval_dashboard/static/src/js/dashboard.js",
            "qlk_approval_dashboard/static/src/xml/dashboard.xml",
            "qlk_approval_dashboard/static/src/scss/dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}
