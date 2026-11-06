
from odoo import fields, models


class ProductRmTdsProperty(models.Model):
    _name = 'product.rm.tds.property'
    _description = 'RM TDS Property'
    _order = 'category, sequence, name'

    name = fields.Char(string='Property Name', required=True)
    category = fields.Selection([
        ('physical', 'Dimensions & Physical Properties'),
        ('material', 'Material & Surface Treatment'),
        ('quality', 'Barrier & Quality Metrics'),
    ], string='Category', required=True, index=True)

    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
