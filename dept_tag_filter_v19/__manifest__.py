{
    "name": "TAM User Customer Industry Filter on Sale Order",
    "version": "19.0.1.0.0",
    "category": "Customizations",
    "author": "Softeko_Lamia",
    "summary": "Filter Sale Order customers using industries configured per user",
    "depends": ["sale", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_department_views.xml",
        "views/res_users_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
