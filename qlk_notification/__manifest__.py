# -*- coding: utf-8 -*-
{
    "name": "Noto Notification Center",
    "version": "18.0.1.0.0",
    "summary": "Persistent orange notification banner with audio alerts for sessions, cases, consultations, reports, payments, and more.",
    "author": "Codex",
    "website": "https://example.com",
    "category": "Productivity",
    "depends": ["base", "mail", "bus", "web", "qlk_law"],
    "data": [
        "security/ir.model.access.csv",
        "views/notification_item_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_notification/static/src/js/sticky_notifier.js",
            "qlk_notification/static/src/xml/sticky_notifier.xml",
            "qlk_notification/static/src/scss/sticky_notifier.scss",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    # "post_init_hook": "post_init_hook",
}
