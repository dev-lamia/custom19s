from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rm_tds_physical_line_ids = fields.One2many(
        'product.rm.tds.physical.line', 'product_tmpl_id',
        string='Dimensions & Physical Properties', copy=True,
    )
    rm_tds_text_line_ids = fields.One2many(
        'product.rm.tds.text.line', 'product_tmpl_id',
        string='Material & Surface Treatment', copy=True,
    )
    rm_tds_quality_line_ids = fields.One2many(
        'product.rm.tds.quality.line', 'product_tmpl_id',
        string='Barrier & Quality Metrics', copy=True,
    )
