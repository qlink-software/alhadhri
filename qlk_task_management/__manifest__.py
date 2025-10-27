# -*- coding: utf-8 -*-
{
    "name": "QLK Task & Hours Management",
    "version": "18.0.1.0.0",
    "summary": "Track tasks and billable hours across litigation, corporate, and management activities.",
    "description": """
Implements unified task capture with approvals and hour tracking for litigation cases,
corporate engagements, and internal management work. Integrates with HR employees,
provides approval workflows, and surfaces hour summaries in related records.
""",
    "author": "Codex",
    "website": "https://www.example.com",
    "category": "Services",
    "license": "OPL-1",
    "depends": [
        "mail",
        "hr",
        "qlk_law",
        "qlk_engagement_letter",
    ],
    "data": [
        "security/task_security.xml",
        "security/ir.model.access.csv",
        "views/task_views.xml",
        "views/case_views.xml",
        "views/engagement_views.xml",
        "views/hr_employee_views.xml",
        "views/task_menu.xml",
    ],
    "installable": True,
    "application": False,
}
