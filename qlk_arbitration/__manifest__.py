# -*- coding: utf-8 -*-
{
    "name": "QLK Arbitration Legal",
    "version": "18.0.1.1.1",
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
        "qlk_security_base",
        "qlk_law",
    ],
    "data": [
        "security/security.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "views/arbitration_menu_views.xml",
    ],
    "installable": True,
    "application": True,
}
