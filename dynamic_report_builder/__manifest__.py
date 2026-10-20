{
    'name': 'Dynamic Report Builder',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Select any model and fields to generate a dynamic printable report',
    'description': """
Dynamic Report Builder
=======================
- Select a main model and build report columns in your own sequence
- Drag and reorder columns exactly as they should appear in the PDF
- Select fields from the main model or from relational line models
- Each report configuration keeps its own dedicated QWeb template
- Professional guided builder with quick fields, standard domain editor, sorting and runtime date/user filters
- Uses the company Configure Document Layout settings for PDF styling
""",
    'author': 'Softeko_Lamia',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'dynamic_report_builder/static/src/scss/date_filter_wizard.scss',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'report/dynamic_report_templates.xml',
        'report/dynamic_report.xml',
        'views/report_wizard_views.xml',
        'views/date_filter_wizard_views.xml',
        'data/runtime_action_sync.xml',
    ],
    'icon': '/dynamic_report_builder/static/description/icon.png',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
