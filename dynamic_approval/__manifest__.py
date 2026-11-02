{
    'name': 'Dynamic Approval',
    'version': '19.0.1.0.12',
    'category': 'Customizations',
    'summary': 'Standallone approval workflow for any Odoo object button',
    'description': '''
Professional standalone dynamic approval system.
Configure approvers separately from Odoo built-in Approvals and protect any
object button on selected business models.
''',
    'author': 'Softeko_Lamia',
    'depends': [
        'base',
        'mail',
        'web',
        'sale_management',
        'purchase',
        'account',
        'stock',
        'crm',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/cleanup_legacy_views.xml',
        'views/approval_popup_views.xml',
        'views/approval_rule_views.xml',
        'views/approval_request_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamic_approval/static/src/js/approval_error_handler.js',
            'dynamic_approval/static/src/js/approval_button_state.js',
            'dynamic_approval/static/src/js/approval_activity_mark_done_v18.js',
            'dynamic_approval/static/src/xml/approval_activity_mark_done_v18.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
