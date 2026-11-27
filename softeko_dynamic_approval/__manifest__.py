{
    'name': 'Dynamic Approval',
    'version': '19.0.1.0.12',
    'category': 'Customizations',
    'summary': 'Standalone approval workflow for any Odoo object button',
    'description': '''
Professional standalone dynamic approval system.
Configure approvers separately from Odoo built-in Approvals and protect any
object button on selected business models.
''',
    'author': 'Softeko',
    'maintainer': 'Softeko',
    'website': 'https://www.softeko.co/',
    'support': 'contact@softeko.co',
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
            'softeko_dynamic_approval/static/src/js/approval_error_handler.js',
            'softeko_dynamic_approval/static/src/js/approval_button_state.js',
            'softeko_dynamic_approval/static/src/js/approval_activity_mark_done_v18.js',
            'softeko_dynamic_approval/static/src/xml/approval_activity_mark_done_v18.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'images': ['static/description/images/cover_animation.gif'],
}
