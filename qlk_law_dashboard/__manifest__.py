# -*- coding: utf-8 -*-
{
    "name": "QLK Lawyer Dashboard",
    "version": "1.0.0",
    "summary": "Personalized dashboard for lawyers with cases, hearings, consultations, complaints and KPIs.",
    "description": "Adds a modern dashboard for lawyers that highlights their related cases, hearings, consultations, complaints, and task hours.",
    "author": "Codex",
    "website": "https://www.example.com",
    "category": "Law",
    "license": "OPL-1",
    "depends": [
        "web",
        "mail",
        "hr",
        "hr_holidays",
        "qlk_law",
        "qlk_law_police",
    ],
    "data": [
        "views/lawyer_dashboard_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_law_dashboard/static/src/js/lawyer_dashboard.js",
            "qlk_law_dashboard/static/src/xml/lawyer_dashboard.xml",
            "qlk_law_dashboard/static/src/scss/lawyer_dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}
