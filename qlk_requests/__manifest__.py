# -*- coding: utf-8 -*-
{
    "name": "QLK Internal Requests",
    "version": "18.0.1.0.0",
    "summary": "Internal request workflow with lawyer dashboard integration.",
    "description": """
Internal Requests
=================
Manage internal requests between users, track workflow status, and surface
request summaries directly in the lawyer dashboard.
""",
    "author": "Qlink",
    "website": "https://www.example.com",
    "category": "Productivity",
    "license": "OPL-1",
    "depends": [
        "mail",
        "qlk_law_dashboard",
    ],
    "data": [
        "security/request_security.xml",
        "security/ir.model.access.csv",
        "views/request_views.xml",
        "views/request_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_requests/static/src/xml/request_dashboard.xml",
            "qlk_requests/static/src/scss/request_dashboard.scss",
        ],
    },
    "installable": True,
    "application": True,
}
