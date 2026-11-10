from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .limits import guess_limits

# Workbook "Catalogs error" codes that belong to each incoming test.
# Tests not listed offer the whole catalog until QC narrows them on the TDS.
DEFAULT_TEMPLATE_DEFECTS = {
    'qc_template_incoming_003': ['RM001'],           # Film thickness
    'qc_template_incoming_004': ['RM001'],           # Grammage
    'qc_template_incoming_005': ['RM005'],           # Dyne level
    'qc_template_incoming_009': ['RM012'],           # Ink viscosity
    'qc_template_incoming_011': ['RM016'],           # Ink solid content
    'qc_template_incoming_012': ['RM011'],           # Ink colour match
    'qc_template_incoming_014': ['RM013'],           # Solvent water content
    'qc_template_incoming_015': ['RM012', 'RM014'],  # Adhesive viscosity
    'qc_template_incoming_016': ['RM016'],           # Adhesive solid content
    'qc_template_incoming_021': ['RM004'],           # Core ID
    'qc_template_incoming_022': ['RM004'],           # Core wall / crush
    'qc_template_incoming_023': ['RM001'],           # Mounting tape thickness
}


MATERIAL_TYPES = [
    ('film', 'Film Substrates'), ('ink', 'Printing Inks'),
    ('solvent', 'Solvents'), ('adhesive', 'Lamination Adhesives'),
    ('valve', 'Degassing Valves'), ('zipper', 'Zippers'),
    ('core', 'Paper Cores'), ('tape', 'Mounting Tape'),
    ('plate', 'Printing Plates'), ('other', 'Other'),
]


class RmQcUom(models.Model):
    _name = 'rm.qc.uom'
    _description = 'QC Unit of Measure'
    _order = 'name'

    name = fields.Char(string='Unit', required=True, index=True)
    active = fields.Boolean(default=True)
    _name_unique = models.Constraint('UNIQUE(name)', 'This QC unit already exists.')

    @api.model
    def _rm_qc_get_or_create(self, name):
        name = (name or '').strip()
        if not name:
            return self.browse()
        unit = self.with_context(active_test=False).search([('name', '=', name)], limit=1)
        return unit or self.create({'name': name})

    @api.model
    def _rm_qc_sync_master_data(self):
        """Install/upgrade: unit dropdown values, default catalog errors and
        limit types for draft standards. Never touches recorded results."""
        Template = self.env['rm.qc.parameter.template'].with_context(active_test=False)
        Line = self.env['rm.qc.specification.line'].with_context(
            active_test=False, rm_qc_system_update=True)
        Defect = self.env['rm.qc.defect'].with_context(active_test=False)

        for record in Template.search([('uom_id', '=', False), ('uom_text', '!=', False)]):
            record.uom_id = self._rm_qc_get_or_create(record.uom_text)
        for line in Line.search([('uom_id', '=', False), ('uom_text', '!=', False)]):
            line.uom_id = self._rm_qc_get_or_create(line.uom_text)

        for xmlid, codes in DEFAULT_TEMPLATE_DEFECTS.items():
            template = self.env.ref('quality_rm_spec_sampling.%s' % xmlid,
                                    raise_if_not_found=False)
            if template and not template.defect_ids:
                template.defect_ids = [fields.Command.set(
                    Defect.search([('code', 'in', codes)]).ids)]

        drafts = Line.search([('specification_id.state', '=', 'draft')])
        for line in drafts:
            values = {}
            if not line.defect_ids and line.template_id.defect_ids:
                values['defect_ids'] = [fields.Command.set(line.template_id.defect_ids.ids)]
            if line.limit_type == 'reference':
                guess = guess_limits(line.lsl_text, line.target_text, line.usl_text)
                if guess['limit_type'] != 'reference':
                    if line.nominal_set and guess['limit_type'] in ('pct', 'abs'):
                        guess['target_numeric'] = line.nominal_numeric
                    values.update(guess)
            if values:
                line.write(values)
        return True


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
    uom_id = fields.Many2one('rm.qc.uom', string='Unit')
    uom_text = fields.Char(string='UOM', compute='_compute_uom_text', store=True,
                           readonly=False)
    defect_ids = fields.Many2many('rm.qc.defect', 'rm_qc_template_defect_rel',
                                  'template_id', 'defect_id', string='Catalog Errors',
                                  help='Errors offered to the inspector for this test.')
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

    @api.depends('uom_id')
    def _compute_uom_text(self):
        for rec in self:
            rec.uom_text = rec.uom_id.name if rec.uom_id else rec.uom_text

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
    _description = 'Product Property Configuration'
    _order = 'material_type, sequence, id'

    material_type = fields.Selection(
        MATERIAL_TYPES, string='RM Material Type', required=True, index=True)
    name = fields.Char(string='Property', required=True)
    uom_text = fields.Char(string='Default Unit')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    def _sync_products_for_types(self, material_types):
        if not material_types:
            return
        products = self.env['product.template'].search([
            ('rm_qc_material_type', 'in', list(material_types)),
        ])
        products._sync_rm_qc_property_lines()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_products_for_types(set(records.mapped('material_type')))
        return records

    def write(self, vals):
        old_types = set(self.mapped('material_type'))
        result = super().write(vals)
        if any(key in vals for key in ('name', 'material_type', 'uom_text',
                                      'sequence', 'active')):
            self._sync_products_for_types(
                old_types | set(self.mapped('material_type')))
        return result

    def unlink(self):
        old_types = set(self.mapped('material_type'))
        result = super().unlink()
        self._sync_products_for_types(old_types)
        return result


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
    active = fields.Boolean(string='Active', default=True)
