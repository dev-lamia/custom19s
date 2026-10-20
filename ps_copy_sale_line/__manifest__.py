{
    "name": "Universal Duplicate Lines",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "summary": "Duplicate One2many rows as new editable Add-a-line records across Odoo.",
    "author": "Softeko_Lamia",
    "category": "Customizations",
    "depends": ["web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "ps_copy_sale_line/static/src/js/x2many_duplicate_line.js",
            "ps_copy_sale_line/static/src/scss/x2many_duplicate_line.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
