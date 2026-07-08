# -*- coding: utf-8 -*-
{
    'name': 'ISD Profile Management',
    'version': '18.0.1.0.0',
    'summary': 'Profile Management System for Users and Managers',
    'description': """
        Profile Management System for Odoo 18.0
        
        This module provides a comprehensive profile management system where:
        - Managers can create profiles with steps and assign them to users
        - Users can select profiles, choose steps, make payments, and track progress
        - Support for payment confirmation and progress monitoring
        - Notification system for updates
        - Reporting capabilities for managers
        
        Features:
        - User profile management with step selection
        - Payment processing with receipt upload
        - Progress tracking and status management
        - Manager dashboard for monitoring
        - Notification system
        - Comprehensive reporting
    """,
    'author': 'Manus AI',
    'website': 'https://intellisyncdata.com',
    'category': 'ISD Modules',
    'depends': ['base', 'mail', 'web', 'portal', 'isd_payment', 'isd_marketing_template'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/profile_views.xml',
        'views/step_views.xml',
        'views/payment_views.xml',
        'views/user_profile_views.xml',
        'views/dashboard_views.xml',
        'views/profile_card_views.xml',
        'views/service_package_form.xml',
        'views/manager_interface.xml',
        'views/step_selection_simple.xml',
        'views/pm_config_views.xml',
        'views/menu_items.xml',
        'views/menu_items_override.xml',
        'wizard/payment_rejection_wizard_view.xml',
        'wizard/step_selection_wizard_view.xml',
        'wizard/qr_popup_wizard_view.xml',
        'wizard/profile_api_doc_wizard_view.xml',
        'wizard/payment_method_select_wizard_view.xml',
        'reports/profile_report.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'isd_profile_management/static/src/css/profile_management.css',
            'isd_profile_management/static/src/js/profile_management.js',
        ],
        'web.assets_backend': [
            'isd_profile_management/static/src/js/qr_poll.js',
            'isd_profile_management/static/src/js/payment_method_picker.js',
            'isd_profile_management/static/src/css/payment_method_picker.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}