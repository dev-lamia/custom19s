from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .limits import LIMIT_TYPES, NUMERIC_TYPES, evaluate, limit_display


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    rm_qc_specification_id = fields.Many2one(
        'rm.qc.specification', string='Active QC Standard', index=True,
        domain="[('state','=','approved')]")
    rm_qc_scope = fields.Selection([('incoming', 'Incoming RM'), ('production', 'Production')],
                                   string='QC Scope', default='incoming')
    rm_qc_parameter_line_ids = fields.One2many(
        'rm.qc.inspection.parameter', 'quality_check_id', string='Sampling / Inspection Log')
    rm_qc_production_id = fields.Many2one('mrp.production', string='Manufacturing Order',
                                          ondelete='set null')
    rm_qc_stage = fields.Char(string='Production QC Stage')
    rm_qc_date = fields.Datetime(string='Inspection Date', default=fields.Datetime.now,
                                 readonly=True)
    rm_qc_inspector_id = fields.Many2one('res.users', string='QC Inspector',
                                        default=lambda s: s.env.user)
    rm_qc_review_notes = fields.Text(string='QC Review / Observations')
    rm_qc_po_reference = fields.Char(string='PO Number', compute='_compute_rm_qc_po')
    rm_qc_batch_reference = fields.Char(string='Batch Number', compute='_compute_rm_qc_batch',
                                        store=True)
    rm_qc_progress = fields.Float(string='Results Entered (%)',
                                  compute='_compute_rm_qc_progress',
                                  help='Display only: share of required readings already recorded.')
    rm_qc_failed_count = fields.Integer(string='Out-of-Spec Readings',
                                        compute='_compute_rm_qc_progress')
    # Stored result summary (searchable / groupable / reportable)
    rm_qc_reading_total = fields.Integer(string='Readings Required',
                                         compute='_compute_rm_qc_summary', store=True)
    rm_qc_pass_count = fields.Integer(string='Readings Passed',
                                      compute='_compute_rm_qc_summary', store=True)
    rm_qc_oos_count = fields.Integer(string='Readings Out of Spec',
                                     compute='_compute_rm_qc_summary', store=True)
    rm_qc_fail_count = fields.Integer(string='Readings Failed (manual)',
                                      compute='_compute_rm_qc_summary', store=True)
    rm_qc_pending_count = fields.Integer(string='Readings Pending',
                                         compute='_compute_rm_qc_summary', store=True)
    rm_qc_test_total = fields.Integer(string='Tests',
                                      compute='_compute_rm_qc_summary', store=True)
    rm_qc_test_pass_count = fields.Integer(string='Tests Passed',
                                           compute='_compute_rm_qc_summary', store=True)
    rm_qc_test_fail_count = fields.Integer(string='Tests Not OK',
                                           compute='_compute_rm_qc_summary', store=True)

    @api.constrains('picking_id', 'product_id', 'lot_ids',
                    'rm_qc_specification_id', 'rm_qc_scope')
    def _check_unique_incoming_rm_inspection(self):
        """Do not permit two RM inspections for one receipt/product/batch.

        Keep native Quality Point checks outside this constraint: Odoo can
        legitimately create those for other inspection plans.
        """
        for check in self:
            if (check.rm_qc_scope != 'incoming' or
                    not check.picking_id or not check.product_id or
                    not check.rm_qc_specification_id):
                continue
            lot_condition = (
                ('lot_ids', 'in', check.lot_ids.ids)
                if check.lot_ids else ('lot_ids', '=', False)
            )
            duplicate = self.search([
                ('id', '!=', check.id),
                ('picking_id', '=', check.picking_id.id),
                ('product_id', '=', check.product_id.id),
                ('rm_qc_specification_id', '!=', False),
                lot_condition,
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'An RM QC Inspection already exists for %(product)s on '
                    'receipt %(receipt)s (check %(existing)s). '
                    'Open the existing inspection instead of creating another.'
                ) % {
                    'product': check.product_id.display_name,
                    'receipt': check.picking_id.name,
                    'existing': duplicate.name,
                })

    @api.depends('rm_qc_parameter_line_ids.expected_count',
                 'rm_qc_parameter_line_ids.entered_count',
                 'rm_qc_parameter_line_ids.failed_count')
    def _compute_rm_qc_progress(self):
        for rec in self:
            params = rec.rm_qc_parameter_line_ids
            expected = sum(params.mapped('expected_count'))
            entered = sum(params.mapped('entered_count'))
            rec.rm_qc_progress = min(100.0, entered * 100.0 / expected) if expected else 0.0
            rec.rm_qc_failed_count = sum(params.mapped('failed_count'))

    @api.depends('rm_qc_parameter_line_ids.reading_total',
                 'rm_qc_parameter_line_ids.pass_count',
                 'rm_qc_parameter_line_ids.oos_count',
                 'rm_qc_parameter_line_ids.fail_count',
                 'rm_qc_parameter_line_ids.pending_count',
                 'rm_qc_parameter_line_ids.test_result')
    def _compute_rm_qc_summary(self):
        for rec in self:
            params = rec.rm_qc_parameter_line_ids
            rec.rm_qc_reading_total = sum(params.mapped('reading_total'))
            rec.rm_qc_pass_count = sum(params.mapped('pass_count'))
            rec.rm_qc_oos_count = sum(params.mapped('oos_count'))
            rec.rm_qc_fail_count = sum(params.mapped('fail_count'))
            rec.rm_qc_pending_count = sum(params.mapped('pending_count'))
            rec.rm_qc_test_total = len(params)
            rec.rm_qc_test_pass_count = len(params.filtered(lambda p: p.test_result == 'pass'))
            rec.rm_qc_test_fail_count = len(params.filtered(lambda p: p.test_result == 'fail'))

    @api.depends('picking_id', 'picking_id.origin')
    def _compute_rm_qc_po(self):
        for rec in self:
            rec.rm_qc_po_reference = rec.picking_id.origin or ''

    @api.depends('lot_ids', 'lot_ids.name')
    def _compute_rm_qc_batch(self):
        for rec in self:
            rec.rm_qc_batch_reference = ', '.join(rec.lot_ids.mapped('name'))

    def action_rm_qc_load_specification(self):
        """Populate snapshots only; never overwrite recorded test results."""
        for rec in self:
            if rec.quality_state in ('pass', 'fail'):
                raise UserError(_('Completed checks cannot reload specifications.'))
            if not rec.product_id:
                raise UserError(_('Select the received Product first.'))
            scope = rec.rm_qc_scope or 'incoming'
            spec = rec.rm_qc_specification_id
            if not spec:
                spec = self.env['rm.qc.specification']._find_approved(
                    rec.product_id, scope, rec.rm_qc_stage)
            if not spec:
                raise UserError(_('No active QC Standard found for this product/stage.'))
            if (spec.state != 'approved' or
                    spec.product_tmpl_id != rec.product_id.product_tmpl_id or
                    spec.scope != scope):
                raise UserError(_('Selected specification does not match this product/scope.'))
            if rec.rm_qc_parameter_line_ids:
                raise UserError(_('Inspection parameters already exist; measurements will not be overwritten.'))
            commands = [fields.Command.create({
                'spec_line_id': line.id,
                'name': line.name,
                'uom_text': line.uom_text,
                'lsl_text': line.lsl_text,
                'target_text': line.target_text,
                'usl_text': line.usl_text,
                'limit_mode': line.limit_mode,
                'limit_type': line.limit_type,
                'defect_ids': [fields.Command.set(line.defect_ids.ids)],
                'lsl_numeric': line.lsl_numeric,
                'usl_numeric': line.usl_numeric,
                'inspection_method': line.inspection_method,
                'lot_size': line.lot_size,
                'sample_size': line.sample_size,
                'samples_to_test': line.sample_count,
                'measurements_per_sample': line.measurements_per_sample,
                'sample_method': line.sample_method,
                'inspection_level': line.inspection_level,
                'inspection_frequency': line.inspection_frequency,
            }) for line in spec.line_ids]
            rec.write({'rm_qc_specification_id': spec.id,
                       'rm_qc_parameter_line_ids': commands})
            rec.rm_qc_parameter_line_ids.action_generate_measurements()
        return True

    def _rm_qc_verify_before_pass(self):
        for check in self.filtered('rm_qc_specification_id'):
            if not check.rm_qc_parameter_line_ids:
                raise UserError(_('Load the QC Sampling Log before passing %s.') % check.display_name)
            for parameter in check.rm_qc_parameter_line_ids:
                parameter._verify_complete()
                if any(log.result in ('fail', 'out_of_spec') for log in parameter.log_ids):
                    raise UserError(_('Out-of-spec or failed measurement in %s. '
                                      'Investigate and use Fail; AQL lot disposition is manual.')
                                    % parameter.name)

    def _rm_qc_ready_to_pass(self):
        """All required readings entered and none out of spec / failed."""
        self.ensure_one()
        params = self.rm_qc_parameter_line_ids
        if not self.rm_qc_specification_id or not params:
            return False
        for parameter in params:
            if not parameter.expected_count or parameter.entered_count < parameter.expected_count:
                return False
            if parameter.failed_count:
                return False
        return True

    def _rm_qc_try_auto_pass(self):
        """Workbook: when every reading is within limits the check passes by itself."""
        for check in self:
            if check.quality_state == 'none' and check._rm_qc_ready_to_pass():
                check.do_pass()
        return True

    def write(self, vals):
        if vals.get('quality_state') == 'pass':
            self._rm_qc_verify_before_pass()
        if {'rm_qc_specification_id', 'rm_qc_parameter_line_ids'}.intersection(vals):
            if any(check.quality_state in ('pass', 'fail') for check in self):
                raise UserError(_('Completed QC check specifications are locked.'))
        if 'rm_qc_parameter_line_ids' not in vals:
            return super().write(vals)
        # Save every changed result first, then decide on the automatic Pass.
        result = super(QualityCheck, self.with_context(rm_qc_defer_autopass=True)).write(vals)
        if not self.env.context.get('rm_qc_defer_autopass'):
            self._rm_qc_try_auto_pass()
        return result

    def do_pass(self):
        self._rm_qc_verify_before_pass()
        return super().do_pass()

    def do_measure(self):
        self._rm_qc_verify_before_pass()
        return super().do_measure()


class RmQcInspectionParameter(models.Model):
    _name = 'rm.qc.inspection.parameter'
    _description = 'Quality Check Parameter / Sampling Snapshot'
    _order = 'sequence, id'

    quality_check_id = fields.Many2one('quality.check', string='Quality Check',
                                       required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    spec_line_id = fields.Many2one('rm.qc.specification.line', string='Specification Source',
                                  readonly=True)
    name = fields.Char(string='MIC / Property', required=True)
    uom_text = fields.Char(string='UOM', readonly=True)
    lsl_text = fields.Char(string='LSL', readonly=True)
    target_text = fields.Char(string='Target', readonly=True)
    usl_text = fields.Char(string='USL', readonly=True)
    limit_mode = fields.Selection([('numeric', 'Numeric'), ('reference', 'Reference / Manual')],
                                   string='Assessment', default='reference', readonly=True)
    limit_type = fields.Selection(LIMIT_TYPES, string='Limit Type', default='reference',
                                  readonly=True)
    limit_display = fields.Char(string='Allowed Range', compute='_compute_limit_display')
    defect_ids = fields.Many2many('rm.qc.defect', 'rm_qc_insp_param_defect_rel',
                                  'parameter_id', 'defect_id', string='Catalog Errors',
                                  readonly=True)
    lsl_numeric = fields.Float(string='Numeric LSL', digits=(16, 5), readonly=True)
    usl_numeric = fields.Float(string='Numeric USL', digits=(16, 5), readonly=True)
    inspection_method = fields.Char(string='Inspection Method', readonly=True)
    lot_size = fields.Char(string='Base Inspection Lot Size', readonly=True)
    sample_size = fields.Char(string='Sampling Rule', readonly=True)
    samples_to_test = fields.Integer(string='Actual Samples to Test', default=1,
                                     help='Set this using actual pallets/rolls/batch size.')
    measurements_per_sample = fields.Integer(string='Measurements per Sample', default=1,
                                             readonly=True)
    sample_method = fields.Char(string='Sample Method', readonly=True)
    inspection_level = fields.Char(string='Inspection Level', readonly=True)
    inspection_frequency = fields.Char(string='Inspection Frequency', readonly=True)
    log_ids = fields.One2many('rm.qc.inspection.log', 'parameter_id', string='Measurement Logs')
    expected_count = fields.Integer(string='Readings Needed', compute='_compute_rm_qc_progress')
    entered_count = fields.Integer(string='Readings Done', compute='_compute_rm_qc_progress')
    failed_count = fields.Integer(string='Out-of-Spec Readings', compute='_compute_rm_qc_progress')
    progress = fields.Float(string='Progress', compute='_compute_rm_qc_progress',
                            help='Display only: percentage of required readings recorded.')
    reading_total = fields.Integer(string='Readings', compute='_compute_reading_summary',
                                   store=True)
    pass_count = fields.Integer(string='Pass', compute='_compute_reading_summary', store=True)
    oos_count = fields.Integer(string='Out of Spec', compute='_compute_reading_summary',
                               store=True)
    fail_count = fields.Integer(string='Fail', compute='_compute_reading_summary', store=True,
                                help='Visual / manual readings marked Fail.')
    pending_count = fields.Integer(string='Pending', compute='_compute_reading_summary',
                                   store=True)
    test_result = fields.Selection([('pending', 'Pending'), ('pass', 'OK'),
                                    ('fail', 'Not OK')], string='Test Result',
                                   compute='_compute_reading_summary', store=True)

    @api.depends('samples_to_test', 'measurements_per_sample',
                 'log_ids.result', 'log_ids.sample_no', 'log_ids.measure_no')
    def _compute_rm_qc_progress(self):
        for rec in self:
            samples = max(rec.samples_to_test or 0, 0)
            per_sample = max(rec.measurements_per_sample or 0, 0)
            expected = samples * per_sample
            done = {(log.sample_no, log.measure_no) for log in rec.log_ids
                    if log.result != 'pending'
                    and 1 <= log.sample_no <= samples
                    and 1 <= log.measure_no <= per_sample}
            rec.expected_count = expected
            rec.entered_count = len(done)
            rec.failed_count = len(rec.log_ids.filtered(
                lambda log: log.result in ('fail', 'out_of_spec')))
            rec.progress = min(100.0, len(done) * 100.0 / expected) if expected else 0.0

    @api.depends('samples_to_test', 'measurements_per_sample',
                 'log_ids.result', 'log_ids.sample_no', 'log_ids.measure_no')
    def _compute_reading_summary(self):
        for rec in self:
            samples = max(rec.samples_to_test or 0, 0)
            per_sample = max(rec.measurements_per_sample or 0, 0)
            latest = {}
            for log in rec.log_ids:
                if 1 <= log.sample_no <= samples and 1 <= log.measure_no <= per_sample:
                    latest[(log.sample_no, log.measure_no)] = log.result
            results = list(latest.values())
            rec.reading_total = samples * per_sample
            rec.pass_count = results.count('pass')
            rec.oos_count = results.count('out_of_spec')
            rec.fail_count = results.count('fail')
            rec.pending_count = max(rec.reading_total - rec.pass_count
                                    - rec.oos_count - rec.fail_count, 0)
            if rec.oos_count or rec.fail_count:
                rec.test_result = 'fail'
            elif rec.pending_count or not rec.reading_total:
                rec.test_result = 'pending'
            else:
                rec.test_result = 'pass'

    @api.depends('limit_type', 'lsl_numeric', 'usl_numeric', 'uom_text',
                 'lsl_text', 'usl_text', 'target_text')
    def _compute_limit_display(self):
        for rec in self:
            rec.limit_display = limit_display(rec.limit_type, rec.lsl_numeric, rec.usl_numeric,
                                              rec.uom_text, rec.lsl_text, rec.usl_text,
                                              rec.target_text)

    @api.onchange('samples_to_test')
    def _onchange_samples_to_test(self):
        """Show the extra sample rows immediately; no extra button needed."""
        for rec in self:
            if not (1 <= (rec.samples_to_test or 0) <= 1000):
                continue
            existing = {(log.sample_no, log.measure_no) for log in rec.log_ids}
            commands = [fields.Command.create({'sample_no': sample_no, 'measure_no': measure_no})
                        for sample_no in range(1, rec.samples_to_test + 1)
                        for measure_no in range(1, (rec.measurements_per_sample or 1) + 1)
                        if (sample_no, measure_no) not in existing]
            if commands:
                rec.log_ids = commands

    @api.constrains('samples_to_test')
    def _check_samples(self):
        for rec in self:
            if rec.samples_to_test < 1 or rec.samples_to_test > 1000:
                raise ValidationError(_('Samples to Test must be 1–1000.'))

    def action_open_measurement_logs(self):
        """Open the relevant TDS property directly from the QC summary list."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sample Measurements - %s') % self.name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(
                self.env.ref(
                    'quality_rm_spec_sampling.view_rm_qc_inspection_parameter_form'
                ).id, 'form',
            )],
            'target': 'new',
        }

    def action_generate_measurements(self):
        for rec in self:
            if rec.quality_check_id.quality_state in ('pass', 'fail'):
                raise UserError(_('A completed check cannot generate new measurements.'))
            expected = rec.samples_to_test * rec.measurements_per_sample
            if expected > 3000:
                raise UserError(_('Too many measurements. Split the QC inspection into batches.'))
            existing = {(line.sample_no, line.measure_no) for line in rec.log_ids}
            vals = [{
                'parameter_id': rec.id,
                'sample_no': sample_no,
                'measure_no': measure_no,
            } for sample_no in range(1, rec.samples_to_test + 1)
              for measure_no in range(1, rec.measurements_per_sample + 1)
              if (sample_no, measure_no) not in existing]
            if vals:
                self.env['rm.qc.inspection.log'].create(vals)
        return True

    def _verify_complete(self):
        self.ensure_one()
        expected = {(s, m) for s in range(1, self.samples_to_test + 1)
                    for m in range(1, self.measurements_per_sample + 1)}
        valid = {(line.sample_no, line.measure_no) for line in self.log_ids
                 if line.result != 'pending'}
        if not expected.issubset(valid):
            raise UserError(_('Incomplete %s: expected %d measured values. '
                              'Click Generate Logs and fill each result.')
                            % (self.name, len(expected)))

    def write(self, vals):
        if any(rec.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Completed inspection lines are locked.'))
        result = super(RmQcInspectionParameter,
                       self.with_context(rm_qc_defer_autopass=True)).write(vals)
        if not self.env.context.get('rm_qc_defer_autopass'):
            self.mapped('quality_check_id')._rm_qc_try_auto_pass()
        return result

    def unlink(self):
        if any(rec.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Cannot delete completed inspection lines.'))
        return super().unlink()


class RmQcInspectionLog(models.Model):
    _name = 'rm.qc.inspection.log'
    _description = 'Per-Sample Per-Measurement QC Log'
    _order = 'parameter_id, sample_no, measure_no, id'

    parameter_id = fields.Many2one('rm.qc.inspection.parameter', required=True,
                                   string='QC Property', ondelete='cascade', index=True)
    sample_no = fields.Integer(string='Sample / Roll #', default=1, required=True)
    measure_no = fields.Integer(string='Measurement / Log #', default=1, required=True)
    value_text = fields.Char(string='Measured Value / Result')
    manual_result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')],
                                     string='Manual Evaluation',
                                     help='Only used for text/formula/complex TDS limits.')
    defect_id = fields.Many2one('rm.qc.defect', string='Catalog Error',
                                domain="[('id', 'in', allowed_defect_ids)]")
    allowed_defect_ids = fields.Many2many('rm.qc.defect', string='Allowed Errors',
                                          compute='_compute_allowed_defect_ids')
    observation = fields.Char(string='Observation')
    result = fields.Selection([
        ('pending', 'Pending'), ('pass', 'Within Spec'),
        ('out_of_spec', 'Out of Spec'), ('fail', 'Failed')],
        string='Evaluation', compute='_compute_result', store=True)
    # Stored context for analysis (pivot / graph by vendor, product, batch, test)
    check_id = fields.Many2one(related='parameter_id.quality_check_id', store=True,
                               index=True, string='Inspection')
    test_name = fields.Char(related='parameter_id.name', store=True, string='Test')
    product_id = fields.Many2one(related='parameter_id.quality_check_id.product_id',
                                 store=True, string='Product')
    picking_id = fields.Many2one(related='parameter_id.quality_check_id.picking_id',
                                 store=True, string='Receipt')
    partner_id = fields.Many2one(related='parameter_id.quality_check_id.picking_id.partner_id',
                                 store=True, string='Vendor')
    batch_reference = fields.Char(
        related='parameter_id.quality_check_id.rm_qc_batch_reference',
        store=True, string='Lot / Batch')
    inspection_date = fields.Datetime(related='parameter_id.quality_check_id.rm_qc_date',
                                      store=True, string='Inspection Date')
    inspector_id = fields.Many2one(related='parameter_id.quality_check_id.rm_qc_inspector_id',
                                   store=True, string='Inspector')
    check_state = fields.Selection(related='parameter_id.quality_check_id.quality_state',
                                   store=True, string='Inspection Status')
    scope = fields.Selection(related='parameter_id.quality_check_id.rm_qc_scope',
                             store=True, string='QC Scope')

    @api.depends('parameter_id', 'parameter_id.defect_ids')
    def _compute_allowed_defect_ids(self):
        catalog = self.env['rm.qc.defect'].search([])
        for rec in self:
            rec.allowed_defect_ids = rec.parameter_id.defect_ids or catalog

    @api.depends('value_text', 'manual_result', 'parameter_id.limit_mode',
                 'parameter_id.limit_type',
                 'parameter_id.lsl_numeric', 'parameter_id.usl_numeric')
    def _compute_result(self):
        for rec in self:
            if not rec.value_text or not rec.value_text.strip():
                rec.result = 'pending'
                continue
            parameter = rec.parameter_id
            limit_type = parameter.limit_type
            if limit_type not in NUMERIC_TYPES and parameter.limit_mode == 'numeric':
                limit_type = 'minmax'  # snapshot taken before limit types existed
            if limit_type in NUMERIC_TYPES:
                try:
                    number = float(rec.value_text.strip().replace(',', '.'))
                except ValueError:
                    rec.result = 'pending'
                    continue
                within = evaluate(limit_type, number, parameter.lsl_numeric,
                                  parameter.usl_numeric)
                rec.result = 'pass' if within else 'out_of_spec'
            else:
                rec.result = rec.manual_result or 'pending'

    @api.constrains('defect_id', 'value_text', 'manual_result')
    def _check_defect_on_failure(self):
        for rec in self:
            if rec.result in ('out_of_spec', 'fail') and not rec.defect_id:
                raise ValidationError(_(
                    '%(test)s, sample %(sample)s / test %(measure)s is out of spec: '
                    'select the Catalog Error.'
                ) % {'test': rec.parameter_id.name, 'sample': rec.sample_no,
                     'measure': rec.measure_no})
            if (rec.defect_id and rec.parameter_id.defect_ids and
                    rec.defect_id not in rec.parameter_id.defect_ids):
                raise ValidationError(_('%(error)s is not a catalog error for %(test)s.') % {
                    'error': rec.defect_id.display_name, 'test': rec.parameter_id.name})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('rm_qc_defer_autopass'):
            records.mapped('parameter_id.quality_check_id')._rm_qc_try_auto_pass()
        return records

    @api.constrains('sample_no', 'measure_no')
    def _check_index(self):
        for rec in self:
            if rec.sample_no < 1 or rec.measure_no < 1:
                raise ValidationError(_('Sample and measurement numbers must be positive.'))

    def write(self, vals):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Completed inspection logs are locked.'))
        result = super().write(vals)
        if not self.env.context.get('rm_qc_defer_autopass'):
            self.mapped('parameter_id.quality_check_id')._rm_qc_try_auto_pass()
        return result

    def unlink(self):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Cannot delete a completed inspection log.'))
        return super().unlink()
