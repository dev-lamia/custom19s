
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_plate = fields.Boolean(
        string='Plate',
        default=False,
        help='Enable this option to make the product available as a TDS Plate Code.',
    )
