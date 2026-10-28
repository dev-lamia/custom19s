from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


MATERIAL_TYPES = [
    ('film', 'Film Substrates'), ('ink', 'Printing Inks'),
    ('solvent', 'Solvents'), ('adhesive', 'Lamination Adhesives'),
    ('valve', 'Degassing Valves'), ('zipper', 'Zippers'),
    ('core', 'Paper Cores'), ('tape', 'Mounting Tape'),
    ('plate', 'Printing Plates'), ('other', 'Other'),
]


class RmQcParameterTemplate(models.Model):
    _name = 'rm.qc.parameter.template'
    _description = 'QC Master Test Parameter (Source Workbook)'
    _order = 'scope, process, material_type, sequence, id'

    name = fields.Char(string='MIC / QC Property', required=True, index=True)
    scope = fields.Selection([('incoming', 'Incoming Raw Material'),
                              ('production', 'Production Process')],
                             string='Inspection Scope', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    material_type = fields.Selection(MATERIAL_TYPES, string='RM Material Type', index=True)
    category_text = fields.Char(string='Source Category')
    item_text = fields.Char(string='Source Item / Material')
    process = fields.Char(string='Production Stage')
    uom_text = fields.Char(string='UOM')
    lsl_text = fields.Char(string='LSL (Workbook)')
    target_text = fields.Char(string='Target (Workbook)')
    usl_text = fields.Char(string='USL (Workbook)')
    inspection_method = fields.Char(string='Inspection Method')
    lot_size = fields.Char(string='Base Inspection Lot Size')
    sample_size = fields.Char(string='Sample Size')
    measurements_per_sample = fields.Integer(string='Measurements per Sample', default=1)
    sample_method = fields.Char(string='Sample Method')
    inspection_level = fields.Char(string='Inspection Level')
    inspection_frequency = fields.Char(string='Inspection Frequency')
    source_sheet = fields.Char(string='Source Excel Sheet', readonly=True)
    source_row = fields.Integer(string='Source Excel Row', readonly=True)
    active = fields.Boolean(string='Active', default=True)

    @api.constrains('measurements_per_sample')
    def _check_measurements(self):
        for rec in self:
            if rec.measurements_per_sample < 1:
                raise ValidationError(_('Measurements per Sample must be positive.'))


class RmQcDefect(models.Model):
    _name = 'rm.qc.defect'
    _description = 'RM QC Defect Catalog'
    _order = 'code'
    _rec_name = 'code'

    code = fields.Char(string='Defect Code', required=True, index=True)
    name = fields.Char(string='Defect Description', required=True)
    active = fields.Boolean(default=True)
    _code_unique = models.Constraint('UNIQUE(code)', 'QC defect code must be unique.')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} - {rec.name}' if rec.code else rec.name


class RmQcIdentificationTemplate(models.Model):
    _name = 'rm.qc.identification.template'
    _description = 'Product Identification Field Template'
    _order = 'material_type, sequence'

    material_type = fields.Selection(MATERIAL_TYPES, required=True, index=True)
    name = fields.Char(string='Specification Field', required=True)
    sequence = fields.Integer(default=10)


class RmQcProductIdentification(models.Model):
    _name = 'rm.qc.product.identification'
    _description = 'Product-Specific Technical Identification'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True,
                                     ondelete='cascade', index=True)
    template_id = fields.Many2one('rm.qc.identification.template', string='Field Template')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Property', required=True)
    value = fields.Char(string='Specification Value')
    uom_text = fields.Char(string='UOM')
