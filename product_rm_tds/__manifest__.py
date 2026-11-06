{
    'name': 'Product RM Technical Data Sheet',
    'version': '19.0.1.5.0',
    'summary': 'Raw material specifications on non-Plate products',
    'category': 'Customizations',
    'author': 'Softeko_HUMAYRA',
    'license': 'LGPL-3',
    'depends': ['stock', 'project_plate_tds'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/rm_tds_property.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}
