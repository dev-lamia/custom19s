{
    "name": "Sale Finance Advance Approval",
    "summary": "Finance-controlled quotation approval and advance payment workflow",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Softeko_Lamia",
    "license": "LGPL-3",
    "depends": ["sale_management", "account", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
        "wizard/payment_submit_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
