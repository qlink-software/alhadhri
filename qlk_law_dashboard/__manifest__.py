# -*- coding: utf-8 -*-
{
    "name": "QLK Law Dashboard Alhadhri",
    "version": "18.0.1.0.0",
    "summary": "Employee performance widgets for the Lawyer Dashboard Alhadhri.",
    "description": "Extends the QLINK Lawyer Dashboard with employee hours, target progress, and leave balance cards.",
    "author": "Qlink",
    "website": "https://www.example.com",
    "category": "Law",
    "license": "OPL-1",
    "depends": [
        "web",
        "contacts",
        "hr",
        "hr_holidays",
        "hr_timesheet",
        "hr_qatar",
        "qlk_management",
        "qlk_task_management",
        "qlk_law_qlink_dashboard",
    ],
    "data": [
        "views/hr_employee_views.xml",
        "views/qlk_court_dashboard_menu_inherit.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "qlk_law_dashboard/static/src/xml/lawyer_dashboard_inherit.xml",
            "qlk_law_dashboard/static/src/scss/lawyer_dashboard_extension.scss",
        ],
    },
    "installable": True,
    "application": False,
}
