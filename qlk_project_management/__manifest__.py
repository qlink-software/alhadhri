# -*- coding: utf-8 -*-
{
    "name": "QLK Project Management",
    "version": "18.0.1.0.0",
    "summary": "Project lifecycle for litigation, pre-litigation, arbitration, and corporate matters with task and hour tracking.",
    "description": """
Adds a dedicated project management workspace that links engagement letters, litigation cases,
and corporate matters. Includes POA handling, standardized stage pipelines, automatic subtasks,
and integration with the task & hours module and lawyer dashboard styling.
""",
    "author": "Codex",
    "website": "https://www.example.com",
    "category": "Services",
    "license": "OPL-1",
    "depends": [
        "mail",
        "hr",
        "qlk_law",
        "qlk_task_management",
        "qlk_engagement_letter",
    ],
    "data": [
        "security/project_security.xml",
        "security/ir.model.access.csv",
        "data/project_stage_data.xml",
        "views/project_views.xml",
        "views/project_dashboard_views.xml",
        "views/analysis_dashboard_views.xml",
        "views/project_stage_views.xml",
        "views/task_views.xml",
        "views/menu_views.xml",
        "wizard/transfer_litigation_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_project_management/static/src/scss/project_dashboard.scss",
            "qlk_project_management/static/src/js/project_dashboard.js",
            "qlk_project_management/static/src/xml/project_dashboard.xml",
            "qlk_project_management/static/src/js/analysis_dashboard.js",
            "qlk_project_management/static/src/xml/analysis_dashboard.xml",
        ],
    },
    "installable": True,
    "application": True,
}
