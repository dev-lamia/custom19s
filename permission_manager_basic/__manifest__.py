{'name': 'Access Management',
 'summary': 'Advancedd User, Group & Multi-Company Access Control for Odoo 19',
 'version': '19.0.1.0.8',
 'category': 'Administration/Access Rights',
 'author': 'Softeko_Lamia',
 'maintainer': 'Lamia',
 'license': 'LGPL-3',
 'depends': ['base', 'mail', 'web'],
 'assets': {'web.assets_backend': ['permission_manager_basic/static/src/css/chatter_visibility.css',
                                   'permission_manager_basic/static/src/css/permission_manager_ui.css',
                                   'permission_manager_basic/static/src/js/block_debug_mode.js',
                                   'permission_manager_basic/static/src/js/conditional_action_menus.js',
                                   'permission_manager_basic/static/src/js/spreadsheet_cog_menu_access.js',
                                   'permission_manager_basic/static/src/js/spreadsheet_model_guard.js',
                                   'permission_manager_basic/static/src/js/export_data_dialog_control.js',
                                   'permission_manager_basic/static/src/js/search_menu_access.js',
                                   'permission_manager_basic/static/src/js/view_switcher_access.js',
                                   'permission_manager_basic/static/src/xml/export_data_dialog.xml',
                                   'permission_manager_basic/static/src/xml/search_menu_access.xml',
                                   'permission_manager_basic/static/src/xml/view_switcher_access.xml']},
 'data': ['data/cleanup_stale_assets.xml',
          'security/security.xml',
          'security/ir.model.access.csv',
          'views/permission_manager_views.xml',
          'views/menu_views.xml'],
 'installable': True,
 'application': True,
 'description': 'Access Management for Odoo 19\n'
                '\n'
                'A professional policy-based access control solution by Softeko, developed by '
                'Lamia.\n'
                'Create reusable policies and apply them to individual users, user groups and '
                'company scopes.\n'
                'Control menus, models, fields, records, buttons, tabs, chatter, reports, actions, '
                'views,\n'
                'import/export/spreadsheet behavior and global security settings from one '
                'centralized interface.\n'
                '\n'
                'Key capabilities include:\n'
                '- User and User Group policy assignment\n'
                '- Multi-company policy scope\n'
                '- Menu and submenu visibility control\n'
                '- Model operation restrictions: Read, Create, Edit, Delete, Archive, Unarchive, '
                'Duplicate, Import and Export\n'
                '- Unified Field Controls: hide, read-only, required, import/export, conditions '
                'and relational domain settings in one rule\n'
                '- Domain-based record visibility rules\n'
                '- Button and notebook tab restrictions\n'
                '- Chatter controls for messages, notes, activities, attachments, followers and '
                'follow/unfollow\n'
                '- Report, action and view restrictions, including model-wise view-switcher option '
                'hiding\n'
                '- Model-wise Search Panel controls for Filters, Group By, Favorites, Custom '
                'Filter (panel + autocomplete + facet editor), Custom Group By and Save Current '
                'Search\n'
                '- Global controls including Force Read-Only, Block Debug Mode, Block Login and '
                'Export field browser control\n'
                '- Advanced policy search/filter options and smart-button navigation\n'
                '\n'
                'Product Company: Softeko\n'
                'Developer: Lamia\n'
                'Developer Profile: https://lamia-akter.odoo.com/\n'
                'Company Website: https://www.softeko.co/\n'
                'Compatibility: Odoo 19\n',
 'website': 'https://www.softeko.co/'}
