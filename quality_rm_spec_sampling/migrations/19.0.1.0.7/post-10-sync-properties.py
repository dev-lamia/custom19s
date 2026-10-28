"""On upgrade, sync all existing products with the configured property master."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    products = env['product.template'].search([
        ('rm_qc_material_type', '!=', False),
    ])
    products._sync_rm_qc_property_lines()
