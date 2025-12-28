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
        'crm',
        'hr',
        'project',
        'account',
        'qlk_law',
        'qlk_council_template',
        'qlk_task_management',
        'qlk_corporate',
        'qlk_arbitration',
        'project_hr_skills',
        # 'bd_pdf_builder',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/approval_groups.xml',
        'security/project_security.xml',
        # 'security/managment_security.xml',
        'data/sequence.xml',
        'data/project_stage_data.xml',
        'data/pre_litigation_sequence.xml',
        'data/qlk_project_sequence.xml',
        'data/engagement_cleanup_actions.xml',
        'views/contact.xml',
        # 'views/dashboard_view.xml',
        'reports/agreements_report.xml',
        # 'views/qlk_agreement_view.xml',
        'views/bd_proposal_views.xml',
        'views/bd_engagement_letter_views.xml',
        'views/project_views.xml',
        'views/project_dashboard_views.xml',
        'views/analysis_dashboard_views.xml',
        'views/project_stage_views.xml',
        'views/pre_litigation_views.xml',
        'views/case_views.xml',
        'views/corporate_integration_views.xml',
        'views/arbitration_integration_views.xml',
        'views/task_views.xml',
        'views/qlk_menu_view.xml',
        'views/tasks.xml',
        'views/menu_views.xml',
        'views/crm_lead.xml',
        'views/cost_calculation_views.xml',
        'views/project_task_views.xml',
        'views/sub_project.xml',
        'reports/bd_reports.xml',
        # 'reports/bd_pdf_templates.xml',
        'views/qlk_task_hours_wizard_view.xml',
        'views/project.xml',
        'wizard/project_log_hours_views.xml',
        'wizard/transfer_litigation_views.xml',
        'wizard/transfer_corporate_views.xml',
        'wizard/transfer_arbitration_views.xml',

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
            "qlk_management/static/src/scss/management_dashboard.scss",
            "qlk_management/static/src/js/management_dashboard.js",
            "qlk_management/static/src/xml/management_dashboard.xml",
            "qlk_management/static/src/scss/project_dashboard.scss",
            "qlk_management/static/src/scss/bd_dashboard.scss",
            "qlk_management/static/src/js/project_dashboard.js",
            "qlk_management/static/src/js/bd_dashboard.js",
            "qlk_management/static/src/xml/project_dashboard.xml",
            "qlk_management/static/src/js/analysis_dashboard.js",
            "qlk_management/static/src/xml/analysis_dashboard.xml",
            "qlk_management/static/src/xml/bd_dashboard.xml",
        ],
    },
    # 'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
