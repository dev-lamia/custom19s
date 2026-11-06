from odoo import fields, models


class ProductRmTdsPhysicalLine(models.Model):
    _name = 'product.rm.tds.physical.line'
    _description = 'RM TDS Dimension and Physical Property'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    property_id = fields.Many2one(
        'product.rm.tds.property',
        string='Property',
        domain=[('category', '=', 'physical')],
        required=True,
        ondelete='restrict',
    )

    value_float = fields.Float(string='Value', digits=(16, 4))
    # Retained only to protect data from older releases; not displayed.
    value_integer = fields.Integer(string='Legacy Whole Number')
    value_text = fields.Char(string='Legacy Text Value')



class ProductRmTdsTextLine(models.Model):
    _name = 'product.rm.tds.text.line'
    _description = 'RM TDS Material and Surface Treatment'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)

    property_id = fields.Many2one(
        'product.rm.tds.property',
        string='Property',
        domain=[('category', '=', 'material')],
        required=True,
        ondelete='restrict',
    )

    value_text = fields.Char(string='Value')


class ProductRmTdsQualityLine(models.Model):
    _name = 'product.rm.tds.quality.line'
    _description = 'RM TDS Barrier and Quality Property'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    property_id = fields.Many2one(
        'product.rm.tds.property',
        string='Property',
        domain=[('category', '=', 'quality')],
        required=True,
        ondelete='restrict',
    )
    value_float = fields.Float(string='Value', digits=(16, 4))
    value_text = fields.Char(string='Legacy Range / Text')
