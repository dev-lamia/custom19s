import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .limits import (LIMIT_TYPES, NUMERIC_TYPES, TOLERANCE_PCT, compute_limits,
                     guess_limits, limit_display, _plain_number)


def _safe_number(text):
    """Recognize only explicit numerals; formulae/grades remain review-required."""
    if text is None:
        return None
    value = str(text).strip()
    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?\s*%?', value):
        return float(value.rstrip('%').strip())
    return None


def _sample_count(text):
    """An initial per-unit count, NOT a calculated lot-wide sample requirement."""
    match = re.match(r'\s*(\d+)\s+', text or '')
    return int(match.group(1)) if match else 1


class RmQcSpecification(models.Model):
    _name = 'rm.qc.specification'
    _description = 'Raw Material / Production QC Specification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Specification Reference', required=True, default='New',
                       readonly=True, copy=False)
    product_tmpl_id = fields.Many2one('product.template', string='Product',
                                     required=True, index=True, tracking=True)
    scope = fields.Selection([('incoming', 'Incoming Raw Material'),
                              ('production', 'Production')],
                             string='Scope', required=True, default='incoming', tracking=True)
    process = fields.Char(string='Production Stage',
                          help='For production specifications use the exact process stage.')
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Legacy Submitted'),
                              ('approved', 'Active'), ('archived', 'Archived')],
                             string='Status', default='draft', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda s: s.env.company)
    line_ids = fields.One2many('rm.qc.specification.line', 'specification_id',
                               string='TDS & Sampling Parameters', copy=True)
    intended_customer_id = fields.Many2one('res.partner', string='Intended Customer')
    intended_use = fields.Text(string='Intended Product / Application')
    controller_id = fields.Many2one('res.users', string='QC Controller',
                                   default=lambda s: s.env.user)
    approved_by = fields.Many2one('res.users', string='Activated By', readonly=True,
                                 copy=False)
    approved_on = fields.Datetime(string='Activation Time', readonly=True, copy=False)
    notes = fields.Text(string='TDS / Inspection Notes')
    active = fields.Boolean(default=True)
    _product_spec_unique = models.Constraint(
        'UNIQUE(product_tmpl_id, scope, name, company_id)',
        'Specification reference must be unique for the product and company.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('rm.qc.specification') or 'New'
        records = super().create(vals_list)
        # Workbook: a product has a predefined test table; the user should not
        # need an extra Load button. Existing/supplied lines are never replaced.
        for rec in records:
            if rec.state == 'draft' and not rec.line_ids:
                templates = rec._matching_parameter_templates()
                if templates:
                    rec.write({'line_ids': rec._parameter_commands(templates)})
        return records

    def copy(self, default=None):
        # The workbook requests duplication, not automatic approval/versioning.
        # An Odoo Action > Duplicate must always result in a DRAFT for review.
        defaults = dict(default or {})
        defaults.update({'name': 'New', 'state': 'draft', 'approved_by': False,
                         'approved_on': False, 'active': True})
        return super().copy(defaults)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        # Show predefined tests immediately when opened from a product.
        if 'line_ids' in fields_list and not values.get('line_ids'):
            product_id = (values.get('product_tmpl_id') or
                          self.env.context.get('default_product_tmpl_id'))
            if product_id:
                product = self.env['product.template'].browse(product_id)
                scope = (values.get('scope') or
                         self.env.context.get('default_scope') or 'incoming')
                process = (values.get('process') or
                           self.env.context.get('default_process') or False)
                values['line_ids'] = self._parameter_commands(
                    self._parameter_templates_for(product, scope, process))
        return values

    @api.onchange('product_tmpl_id', 'scope', 'process')
    def _onchange_predefined_tests(self):
        # Pre-fill the test table while creating a standard. Once a saved draft
        # has hand-edited lines, never silently overwrite those values.
        for rec in self:
            if rec.state != 'draft' or (rec._origin.id and rec.line_ids):
                continue
            templates = rec._matching_parameter_templates()
            if rec.product_tmpl_id:
                rec.line_ids = [fields.Command.clear(),
                                *rec._parameter_commands(templates)]

    def _matching_parameter_templates(self):
        self.ensure_one()
        return self._parameter_templates_for(
            self.product_tmpl_id, self.scope, self.process)

    @api.model
    def _parameter_templates_for(self, product, scope, process):
        if not product:
            return self.env['rm.qc.parameter.template']
        material_type = product.rm_qc_material_type
        if scope == 'incoming' and not material_type:
            return self.env['rm.qc.parameter.template']
        if scope == 'production' and not process:
            return self.env['rm.qc.parameter.template']
        domain = [('scope', '=', scope), ('active', '=', True)]
        if scope == 'incoming':
            domain.append(('material_type', '=', material_type))
        else:
            domain.append(('process', '=', process))
        templates = self.env['rm.qc.parameter.template'].search(domain)
        if scope == 'incoming' and material_type == 'film':
            variant = (product.rm_qc_film_type or '').upper()
            if variant:
                templates = templates.filtered(
                    lambda t: bool(re.search(r'\b%s\b' % re.escape(variant),
                                             (t.item_text or '').upper())))
        return templates

    def _parameter_commands(self, templates):
        commands = []
        for t in templates:
            limits = guess_limits(t.lsl_text, t.target_text, t.usl_text)
            commands.append(fields.Command.create({
                'template_id': t.id,
                'name': t.name,
                'uom_id': t.uom_id.id,
                'uom_text': t.uom_text,
                'lsl_text': t.lsl_text,
                'target_text': t.target_text,
                'usl_text': t.usl_text,
                'inspection_method': t.inspection_method,
                'lot_size': t.lot_size,
                'sample_size': t.sample_size,
                'measurements_per_sample': t.measurements_per_sample,
                'sample_method': t.sample_method,
                'inspection_level': t.inspection_level,
                'inspection_frequency': t.inspection_frequency,
                'sample_count': _sample_count(t.sample_size),
                'defect_ids': [fields.Command.set(t.defect_ids.ids)],
                **limits,
            }))
        return commands

    def write(self, vals):
        if vals.get('state') == 'approved':
            if not self.env.user.has_group('base.group_user'):
                raise UserError(_('Only internal users can activate QC standards.'))
        if vals.get('state') == 'archived':
            if not self.env.user.has_group('base.group_user'):
                raise UserError(_('Only internal users can archive QC standards.'))
        protected = {'product_tmpl_id', 'scope', 'process', 'line_ids', 'notes',
                     'intended_use', 'intended_customer_id'}
        if protected.intersection(vals):
            for rec in self:
                if rec.state in ('approved', 'archived'):
                    raise UserError(_('Duplicate this specification to make revisions. '
                                      'Active QC Standard is locked.'))
        return super().write(vals)

    def action_load_parameters(self):
        """Backwards-compatible server action; no longer shown as a UI step."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft specifications can load parameters.'))
            templates = rec._matching_parameter_templates()
            existing = set(rec.line_ids.mapped('template_id').ids)
            missing = templates.filtered(lambda t: t.id not in existing)
            if missing:
                rec.write({'line_ids': rec._parameter_commands(missing)})
        return True

    def action_submit(self):
        """Legacy compatibility only. The module no longer has a submit/manager stage.

        Keep this method because older custom actions may still reference it.
        """
        raise UserError(_(
            'This QC submission step is no longer used. Open the QC Standard '
            'and click Activate Standard instead.'
        ))

    def action_approve(self):
        """Activate a QC standard; optional external dynamic approval hook.

        The object button deliberately retains the action_approve method name
        for upgrades/custom automation while removing built-in manager checks.
        Only the underlying technical validity and draft/legacy-submitted
        state are checked. No external approval is assumed to be installed.
        """
        for rec in self:
            if rec.state not in ('draft', 'submitted'):
                raise UserError(_('Only draft QC standards can be activated.'))
            if not rec.line_ids:
                raise UserError(_('Add at least one QC test before activation.'))
            missing = rec.line_ids.filtered(lambda l: l._rm_qc_target_missing())
            if missing:
                raise UserError(_('Enter the Target value before activation for: %s')
                                % ', '.join(missing.mapped('name')))
            for line in rec.line_ids:
                if line.limit_type in ('pct', 'abs', 'minmax') and line.lsl_numeric > line.usl_numeric:
                    raise ValidationError(_('Incorrect numeric limits for %s.') % line.name)
        self.write({'state': 'approved', 'approved_by': self.env.user.id,
                    'approved_on': fields.Datetime.now()})
        return True

    def action_archive_spec(self):
        self.write({'state': 'archived', 'active': False})
        return True

    def action_duplicate_draft(self):
        self.ensure_one()
        new_spec = self.copy({
            'name': 'New', 'state': 'draft', 'approved_by': False,
            'approved_on': False, 'active': True,
        })
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': new_spec.id, 'view_mode': 'form', 'target': 'current'}

    @api.model
    def _find_approved(self, product, scope='incoming', process=False):
        domain = [
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('scope', '=', scope), ('state', '=', 'approved'),
            ('company_id', '=', self.env.company.id),
        ]
        if scope == 'production':
            domain.append(('process', '=', process))
        return self.search(domain, order='approved_on desc, id desc', limit=1)


class RmQcSpecificationLine(models.Model):
    _name = 'rm.qc.specification.line'
    _description = 'QC Specification Parameter / Sampling Rule'
    _order = 'sequence, id'

    specification_id = fields.Many2one('rm.qc.specification', string='Specification',
                                       required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    template_id = fields.Many2one('rm.qc.parameter.template', string='Master MIC')
    name = fields.Char(string='Test Parameter / MIC', required=True)
    uom_id = fields.Many2one('rm.qc.uom', string='Unit')
    uom_text = fields.Char(string='UOM', compute='_compute_uom_text', store=True,
                           readonly=False)
    lsl_text = fields.Char(string='LSL (TDS text)')
    target_text = fields.Char(string='Target (TDS text)')
    usl_text = fields.Char(string='USL (TDS text)')
    limit_type = fields.Selection(LIMIT_TYPES, string='Limit Type', required=True,
                                  default='minmax',
                                  help='± % / ± amount: type the Target and Min/Max are calculated. '
                                       'Fixed Min/Max: type Min and Max. '
                                       'Visual/Manual: the inspector chooses Pass or Fail.')
    target_numeric = fields.Float(string='Target', digits=(16, 5))
    tolerance_pct = fields.Selection(TOLERANCE_PCT, string='± %')
    tolerance_abs = fields.Float(string='± Amount', digits=(16, 5))
    limit_mode = fields.Selection([
        ('numeric', 'Numeric: compare to verified limits'),
        ('reference', 'TDS Reference: manual assessment')],
        string='Assessment Mode', compute='_compute_limit_mode', store=True)
    nominal_set = fields.Boolean(string='Nominal Value Entered (legacy)', default=False)
    nominal_numeric = fields.Float(string='Nominal Value (legacy)', digits=(16, 5))
    lsl_numeric = fields.Float(string='Min (LSL)', digits=(16, 5),
                               compute='_compute_numeric_limits', store=True, readonly=False)
    usl_numeric = fields.Float(string='Max (USL)', digits=(16, 5),
                               compute='_compute_numeric_limits', store=True, readonly=False)
    limit_display = fields.Char(string='Allowed Range', compute='_compute_limit_display')
    defect_ids = fields.Many2many('rm.qc.defect', 'rm_qc_spec_line_defect_rel',
                                  'line_id', 'defect_id', string='Catalog Errors',
                                  help='Only these errors are offered to the inspector for this test. '
                                       'Leave empty to offer the full catalog.')
    inspection_method = fields.Char(string='Inspection Method')
    lot_size = fields.Char(string='Base Inspection Lot Size')
    sample_size = fields.Char(string='Sample Size Rule')
    sample_count = fields.Integer(string='Initial Samples per Base Unit', default=1,
                                  help='Review based on actual pallets/rolls; All Samples is not automatically calculated.')
    measurements_per_sample = fields.Integer(string='Measurements per Sample', default=1)
    sample_method = fields.Char(string='Sample Method')
    inspection_level = fields.Char(string='Inspection Level / AQL')
    inspection_frequency = fields.Char(string='Inspection Frequency')

    @api.depends('uom_id')
    def _compute_uom_text(self):
        for rec in self:
            rec.uom_text = rec.uom_id.name if rec.uom_id else rec.uom_text

    @api.depends('limit_type')
    def _compute_limit_mode(self):
        for rec in self:
            rec.limit_mode = 'numeric' if rec.limit_type in NUMERIC_TYPES else 'reference'

    @api.depends('limit_type', 'target_numeric', 'tolerance_pct', 'tolerance_abs')
    def _compute_numeric_limits(self):
        for rec in self:
            limits = compute_limits(rec.limit_type, rec.target_numeric,
                                    rec.tolerance_pct, rec.tolerance_abs)
            if limits:
                rec.lsl_numeric, rec.usl_numeric = limits
            else:
                # Fixed / one-sided / visual: keep what the controller typed.
                rec.lsl_numeric = rec.lsl_numeric
                rec.usl_numeric = rec.usl_numeric

    @api.depends('limit_type', 'lsl_numeric', 'usl_numeric', 'uom_text',
                 'lsl_text', 'usl_text', 'target_text')
    def _compute_limit_display(self):
        for rec in self:
            rec.limit_display = limit_display(rec.limit_type, rec.lsl_numeric, rec.usl_numeric,
                                              rec.uom_text, rec.lsl_text, rec.usl_text,
                                              rec.target_text)

    def _rm_qc_target_missing(self):
        """± types need a real Target; 0 is accepted only when the TDS says 0."""
        self.ensure_one()
        if self.limit_type == 'pct':
            return not self.target_numeric
        if self.limit_type == 'abs':
            return not self.target_numeric and _plain_number(self.target_text) is None
        return False

    def action_resolve_nominal_limits(self):
        """Legacy button (no longer shown): limits now calculate automatically."""
        return True

    @api.constrains('sample_count', 'measurements_per_sample', 'lsl_numeric', 'usl_numeric',
                    'limit_type', 'tolerance_pct')
    def _check_validity(self):
        for rec in self:
            if rec.sample_count < 1 or rec.measurements_per_sample < 1:
                raise ValidationError(_('Sample count and measurement count must be positive.'))
            if rec.limit_type == 'minmax' and rec.lsl_numeric > rec.usl_numeric:
                raise ValidationError(_('%s: Min must be less than or equal to Max.') % rec.name)
            if rec.limit_type == 'pct' and not rec.tolerance_pct:
                raise ValidationError(_('%s: choose the ± %% value.') % rec.name)

    def write(self, vals):
        if (not self.env.context.get('rm_qc_system_update') and
                any(rec.specification_id.state in ('approved', 'archived') for rec in self)):
            raise UserError(_('Active QC Standard lines are locked. Duplicate the master.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.specification_id.state in ('approved', 'archived') for rec in self):
            raise UserError(_('Cannot remove active QC Standard lines.'))
        return super().unlink()
