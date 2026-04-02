# -*- coding: utf-8 -*-
{
    'name': "Qlink Backend Theme",
    'author': "Qlink Software",
    'website': "http://www.qlinksoftware.com",
    'category': 'Themes/Backend',
    'version': '18.0.1.0.0',
    'depends': ['web','mail'],
    'data': [
        # 'views/assets.xml',
        # 'views/main_icon.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'qlink_backend_theme_alhadhri/static/src/scss/primary_variables.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/sidebar_custom.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/logo.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/form_sheet.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/model_kanban.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/navbar_menu.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/buttons.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/search_panel.scss',
            'qlink_backend_theme_alhadhri/static/src/js/web_navbar_appmenu/webNavbarAppMenu.js',
            "qlink_backend_theme_alhadhri/static/src/xml/top_bar_templates.xml",

        ],
        'web.assets_frontend': [
            'qlink_backend_theme_alhadhri/static/src/scss/primary_variables.scss',
            'qlink_backend_theme_alhadhri/static/src/scss/login_desgin.scss',
        ]
    },
    'images': ['static/description/icon.jpg'],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
