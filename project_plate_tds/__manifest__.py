{
    'name': 'Project Plate Technical Data Sheet',
    'version': '19.0.1.0.13',
    'category': 'Customizations',
    'author': 'Softeko_HUMAYRA',
    'license': 'LGPL-3',
    'summary': 'Generate Plate TDS from Artwork Project Tasks and GDN',
    'depends': ['sale_management', 'artwork_project', 'crm_requirement_form', 'mail', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/tds_sequence.xml',
        'views/plate_tds_views.xml',
        'views/project_task_views.xml',
        'views/product_template_views.xml',
        'report/plate_tds_report.xml',
        'report/plate_tds_template.xml',
        'views/job_code_views.xml',

    ],
    'assets': {
        'web.assets_backend': ['project_plate_tds/static/src/scss/plate_tds_backend.scss']
        },

    'installable': True,
    'application': False,
}
