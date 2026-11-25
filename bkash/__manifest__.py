{
    'name': 'Bkash Payment Gateway',
    'version': '19.0.1.0.0',
    'summary': 'Accept Bkash payments in Odoo',
    'description': """
Bkash Payment Gateway integration for Odoo.

This module integrates Bkash as an Odoo payment provider. It allows customers
to complete payments using Bkash through Odoo's standard payment flow.

Note:
This module requires a valid Bkash merchant account and API credentials.
    """,
    'category': 'Accounting',
    'author': 'Softeko',
    'maintainer': 'Rifat',
    'website': 'https://www.softeko.co/',
    'support': 'contact@softeko.co',
    'depends': ['payment'],
    'data': [
        'data/payment_method_bkash_data.xml',
        'data/payment_provider_bkash_data.xml',
        'views/payment_provider_views.xml',
    ],
    'assets': {
        'website.assets_frontend': [
            'static/src/js/bkash_redirect.js',
        ],
        'website.assets_frontend_minimal': [
            'static/src/js/bkash_redirect.js',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'price': 20.00,
    'currency': 'USD',
    'license': 'OPL-1',
    'installable': True,
    'application': False,
}