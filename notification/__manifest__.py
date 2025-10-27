# -*- coding: utf-8 -*-
{
    "name": "Noto Notification Center",
    "version": "18.0.1.0.0",
    "summary": "Persistent orange notification banner with audio alerts for sessions, cases, consultations, reports, payments, and more.",
    "author": "Codex",
    "website": "https://example.com",
    "category": "Productivity",
    "depends": ["base", "mail", "bus", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/notification_item_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "notification/static/src/js/sticky_notifier.js",
            "notification/static/src/xml/sticky_notifier.xml",
            "notification/static/src/scss/sticky_notifier.scss",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
