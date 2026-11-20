{
    "name": "Softeko Backend Theme | Odoo 19",
    "summary": "Company branding, favicon, color themes, and MuK-inspired app sidebar",
    "description": """Modern Odoo 19 backend theme with branded navigation, company-wise
favicon and logo controls, color presets, compact mode and optional app sidebar.
Created for Softeko by Lamia Akter. No MuK dependencies required.
""",
    "version": "19.0.1.0.0",
    "category": "Customizations",
    "author": "Lamia Akter, Softeko",
    "maintainer": "Softeko",
    "license": "LGPL-3",
    "depends": ["base_setup", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/web_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "softeko_backend_theme/static/src/scss/backend.scss",
            "softeko_backend_theme/static/src/js/sidebar.js",
            "softeko_backend_theme/static/src/xml/sidebar.xml",
        ],
        "web.assets_frontend": [
            "softeko_backend_theme/static/src/scss/login.scss",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
