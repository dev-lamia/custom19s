{
    'name': 'Artwork Project Flow',
    'version': '19.0.0.1',
    'category': 'Sales/Project',
    'summary': 'Create an artwork project and job-code tasks from confirmed Sales Orders',
    'author': 'Softeko_Lamia',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'project',
        'crm_requirement_form',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/project_task_views.xml',
        'views/project_kanban_views.xml',
        'views/project_task_kanban_views.xml',
        'wizard/artwork_project_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
