# -*- coding: utf-8 -*-
{
    'name': "QLK - Management System",
    'version': '18.0.1.0.0',
    'category': 'QLK - Management',
    'summary': "Manage proposals, agreements, approvals and workflows for law firms",
    'description': """
        Comprehensive management system
        ========================================
        
        Features:
        - Proposal Management with templates
        - Agreement Creation and Tracking
        - Multi-level Approval Workflows
        - Manager Dashboard for tracking progress
        - Client Management
        - Document Management System
        - Time Tracking and Billing Integration
    """,
    'author': "Qlink Software",
    'website': "http://www.qlinksoftware.com",
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'calendar',
        'contacts',
        'sale_crm',
        'sale_pdf_quote_builder',
        'sale_management',
        'hr',
        'sale_crm',
        'hide_chatter',
        'project',
        
    ],
    'data': [
        'security/ir.model.access.csv',
        # 'security/managment_security.xml',
        'data/sequence.xml',
        'data/proposal_email_template.xml',
        # 'views/dashboard_view.xml',
        'reports/report_menu.xml',
        'reports/agreements_report.xml',
        'views/qlk_agreement_view.xml',
        'views/qlk_proposal_view.xml',
        'views/qlk_menu_view.xml',
        'views/crm_lead.xml',
        'views/contact.xml',
        'views/tasks.xml',
        'views/main_project.xml',
        'views/sub_project.xml',
        
        'views/project.xml',
        'views/cost_calculation.xml',

        # 'views/sound_notification_template.xml',
        # 'views/res_config_settings_views.xml',
        # 'wizard/proposal_approval_wizard_views.xml',
        # 'wizard/agreement_generation_wizard_views.xml',
        
    ],
   
    'assets': {
        'web.assets_backend': [
            # 'qlk_management/static/src/css/dashboard.css',
            # 'qlk_management/static/src/js/dashboard.js',
            # 'qlk_management/static/src/xml/dashboard_template.xml',
            "qlk_management/static/src/js/play_sound_with_notification.js",
            # "qlk_management/static/src/js/sound_notification.js",
            "qlk_management/static/src/xml/sound_notification_template.xml",
        ],
    },
    # 'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}