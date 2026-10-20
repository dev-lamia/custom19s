# -*- coding: utf-8 -*-
{
    "name": "Flexible Chatter Panel",
    "summary": "Resize, hide, and switch the form chatter between responsive and bottom modes.",
    "version": "19.0.1.0.12",
    "category": "Customizations",
    "author": "Softeko_HUMAYRA",
    "license": "LGPL-3",
    "depends": ["web", "mail", "base"],
    "data": [
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fcp_good/static/src/js/chatter_panel.js",
            "fcp_good/static/src/scss/chatter_panel.scss",
        ],
    },
    "installable": True,
    "application": False,
}
