# -*- coding: utf-8 -*-
{
    "name": "QLK Corporate Legal",
    "version": "1.0.0",
    "summary": "Corporate legal case management (companies, contracts, consultations).",
    "description": "Manages corporate legal matters including company cases, contracts, consultations, and documents.",
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
        "views/corporate_menu_views.xml",
    ],
    "installable": True,
    "application": True,
}
