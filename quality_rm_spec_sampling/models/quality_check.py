from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    # Technical reference kept for old QC records only. New checks never use TDS.
    rm_qc_is_custom = fields.Boolean(string='RM QC Inspection', default=False,
                                     index=True, copy=False)
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
    rm_qc_batch_reference = fields.Char(string='Batch Number', compute='_compute_rm_qc_batch')

    @api.depends('picking_id', 'picking_id.origin')
    def _compute_rm_qc_po(self):
        for rec in self:
            rec.rm_qc_po_reference = rec.picking_id.origin or ''

    @api.depends('lot_ids', 'lot_ids.name')
    def _compute_rm_qc_batch(self):
        for rec in self:
            rec.rm_qc_batch_reference = ', '.join(rec.lot_ids.mapped('name'))

    def action_rm_qc_load_tests(self):
        """Load the current category/stage master directly, once per QC check.

        Existing logged measurements are never overwritten by master updates.
        """
        for rec in self:
            if rec.quality_state in ('pass', 'fail'):
                raise UserError(_('Completed checks cannot reload QC tests.'))
            if rec.rm_qc_parameter_line_ids:
                continue
            if not rec.product_id:
                raise UserError(_('Select a product first.'))
            rules = self.env['rm.qc.parameter.template'].applicable_to(
                rec.product_id, rec.rm_qc_scope, rec.rm_qc_stage)
            rec.write({
                'rm_qc_is_custom': True,
                'rm_qc_parameter_line_ids': rules.inspection_commands(rec.product_id),
            })
            rec.rm_qc_parameter_line_ids.action_generate_measurements()
        return True

    def action_rm_qc_load_specification(self):
        """Compatibility alias for old custom server actions."""
        return self.action_rm_qc_load_tests()

    def _rm_qc_verify_before_pass(self):
        for check in self.filtered(
                lambda c: c.rm_qc_is_custom or c.rm_qc_specification_id):
            if not check.rm_qc_parameter_line_ids:
                raise UserError(_('No QC tests are loaded for %s. Open the receipt and click QC Inspection.') % check.display_name)
            for parameter in check.rm_qc_parameter_line_ids:
                parameter._verify_complete()
                if any(log.result in ('fail', 'out_of_spec') for log in parameter.log_ids):
                    raise UserError(_('Out-of-spec or failed measurement in %s. '
                                      'Investigate and use Fail; AQL lot disposition is manual.')
                                    % parameter.name)

    def write(self, vals):
        if vals.get('quality_state') == 'pass':
            self._rm_qc_verify_before_pass()
        if {'rm_qc_parameter_line_ids'}.intersection(vals):
            if any(check.quality_state in ('pass', 'fail') for check in self):
                raise UserError(_('Completed QC inspection measurements are locked.'))
        return super().write(vals)

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
    # Legacy pointer retained for historical measurements only.
    spec_line_id = fields.Many2one('rm.qc.specification.line', string='Legacy Source',
                                  readonly=True)
    master_parameter_id = fields.Many2one('rm.qc.parameter.template',
                                         string='QC Rule Source', readonly=True)
    name = fields.Char(string='QC Test', required=True)
    uom_text = fields.Char(string='UOM', readonly=True)
    lsl_text = fields.Char(string='LSL', readonly=True)
    target_text = fields.Char(string='Target', readonly=True)
    usl_text = fields.Char(string='USL', readonly=True)
    limit_mode = fields.Selection([('numeric', 'Numeric'), ('reference', 'Reference / Manual')],
                                   string='Assessment', default='reference', readonly=True)
    lsl_numeric = fields.Float(string='Numeric LSL', digits=(16, 5), readonly=True)
    usl_numeric = fields.Float(string='Numeric USL', digits=(16, 5), readonly=True)
    inspection_method = fields.Char(string='Inspection Method', readonly=True)
    lot_size = fields.Char(string='Base Inspection Lot Size', readonly=True)
    sample_size = fields.Char(string='Sampling Instructions', readonly=True)
    samples_to_test = fields.Integer(string='Actual Samples to Test', default=1,
                                     help='Set this using actual pallets/rolls/batch size.')
    measurements_per_sample = fields.Integer(string='Measurements per Sample', default=1,
                                             readonly=True)
    sample_method = fields.Char(string='Sample Method', readonly=True)
    inspection_level = fields.Char(string='Inspection Level', readonly=True)
    inspection_frequency = fields.Char(string='Inspection Frequency', readonly=True)
    log_ids = fields.One2many('rm.qc.inspection.log', 'parameter_id', string='Measurement Logs')

    progress_display = fields.Char(
        string='Progress', compute='_compute_measurement_progress',
    )
    missing_row_count = fields.Integer(
        string='Missing Measurement Rows', compute='_compute_measurement_progress',
    )
    duplicate_row_count = fields.Integer(
        string='Duplicate Measurement Rows', compute='_compute_measurement_progress',
    )

    @api.depends('samples_to_test', 'measurements_per_sample',
                 'log_ids.sample_no', 'log_ids.measure_no', 'log_ids.result')
    def _compute_measurement_progress(self):
        for rec in self:
            expected = {(s, m) for s in range(1, rec.samples_to_test + 1)
                        for m in range(1, rec.measurements_per_sample + 1)}
            actual = [(line.sample_no, line.measure_no) for line in rec.log_ids]
            recorded = {pair for line in rec.log_ids
                        if line.result != 'pending'
                        for pair in [(line.sample_no, line.measure_no)]}
            rec.missing_row_count = len(expected.difference(actual))
            rec.duplicate_row_count = len(actual) - len(set(actual))
            rec.progress_display = _('%(done)s / %(total)s completed') % {
                'done': len(expected.intersection(recorded)),
                'total': len(expected),
            }


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
        actual = [(line.sample_no, line.measure_no) for line in self.log_ids]
        if len(actual) != len(set(actual)):
            raise UserError(_(
                'Duplicate sample/test rows in %s. Delete the extra row, '
                'then complete the missing measurement.'
            ) % self.name)
        unexpected = set(actual) - expected
        if unexpected:
            raise UserError(_(
                'There are measurements outside the selected sample count in %s. '
                'Review the rows before passing.'
            ) % self.name)
        valid = {(line.sample_no, line.measure_no) for line in self.log_ids
                 if line.result != 'pending'}
        if not expected.issubset(valid):
            raise UserError(_(
                'Incomplete %s: %d of %d results entered. '
                'Open Enter Results and fill the missing measurements.'
            ) % (self.name, len(expected.intersection(valid)), len(expected)))

    def write(self, vals):
        if any(rec.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Completed inspection lines are locked.'))
        return super().write(vals)

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
    defect_id = fields.Many2one('rm.qc.defect', string='Catalog Error')
    observation = fields.Char(string='Observation')
    result = fields.Selection([
        ('pending', 'Pending'), ('pass', 'Within Spec'),
        ('out_of_spec', 'Out of Spec'), ('fail', 'Failed')],
        string='Evaluation', compute='_compute_result', store=True)

    @api.depends('value_text', 'manual_result', 'parameter_id.limit_mode',
                 'parameter_id.lsl_numeric', 'parameter_id.usl_numeric')
    def _compute_result(self):
        for rec in self:
            if not rec.value_text or not rec.value_text.strip():
                rec.result = 'pending'
                continue
            if rec.parameter_id.limit_mode == 'numeric':
                try:
                    number = float(rec.value_text.strip())
                except ValueError:
                    rec.result = 'pending'
                    continue
                rec.result = ('pass' if rec.parameter_id.lsl_numeric <= number
                              <= rec.parameter_id.usl_numeric else 'out_of_spec')
            else:
                rec.result = rec.manual_result or 'pending'

    @api.constrains('sample_no', 'measure_no')
    def _check_index(self):
        for rec in self:
            if rec.sample_no < 1 or rec.measure_no < 1:
                raise ValidationError(_('Sample and measurement numbers must be positive.'))

    @api.constrains('parameter_id', 'sample_no', 'measure_no')
    def _check_unique_measurement_row(self):
        for rec in self:
            duplicate = self.search_count([
                ('parameter_id', '=', rec.parameter_id.id),
                ('sample_no', '=', rec.sample_no),
                ('measure_no', '=', rec.measure_no),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Sample %(sample)s / Test %(test)s already exists. '
                    'Enter the result in the existing row.'
                ) % {'sample': rec.sample_no, 'test': rec.measure_no})

    def write(self, vals):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Completed inspection logs are locked.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Cannot delete a completed inspection log.'))
        return super().unlink()
