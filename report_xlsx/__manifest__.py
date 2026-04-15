# -*- coding: utf-8 -*-
{
    "name": "Base Report XLSX",
    "summary": "Base module to create XLSX reports",
    "author": "ACSONE SA/NV, Odoo Community Association (OCA), Qlink Software",
    "website": "https://www.odoo.com",
    "category": "Reporting",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "depends": [
        "base",
        "web",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "assets": {
        "web.assets_backend": [
            "report_xlsx/static/src/js/report/action_manager_report.esm.js",
        ],
    },
    "installable": True,
}
