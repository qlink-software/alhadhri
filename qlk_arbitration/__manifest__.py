# -*- coding: utf-8 -*-
{
    "name": "QLK Arbitration Legal",
    "version": "1.0.0",
    "summary": "Arbitration case management with sessions, memos, awards, and arbitrator registry.",
    "description": "Manages arbitration disputes including sessions, submissions, awards, and arbitrator records.",
    "author": "Codex",
    "website": "https://www.example.com",
    "category": "Law",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "qlk_law",
    ],
    "data": [
        "security/access_rules.xml",
        "security/ir.model.access.csv",
        "views/arbitration_menu_views.xml",
    ],
    "installable": True,
    "application": True,
}
