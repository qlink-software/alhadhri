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
        # 'views/hide_main_navbar.xml',

    ],
    'assets': {
        'web.assets_backend': [
            # 'qlink_backend_theme/static/src/scss/theme.scss',
            "qlink_backend_theme/static/src/xml/top_bar_templates.xml",
            'qlink_backend_theme/static/src/scss/sidebar.scss',
            'qlink_backend_theme/static/src/js/web_navbar_appmenu/webNavbarAppMenu.js'
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
