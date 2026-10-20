# -*- coding: utf-8 -*-
{
    "name": "TAM Documents Type for Sale & Purchase",
    "summary": "Adds Supplier Documents tab to Sales Orders and Purchase Orders with document types.",
    "version": "19.0.0.0.0",
    "category": "Customizations",
    "author": "Softeko_RIFAT",
    "license": "LGPL-3",
    "depends": ["sale_management", "purchase","hr", "mail", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/supplier_document_type_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
        "views/res_partner_views.xml",
        "data/vendor_document_expiry_cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}