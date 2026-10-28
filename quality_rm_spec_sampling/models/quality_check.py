from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    rm_qc_specification_id = fields.Many2one(
        'rm.qc.specification', string='Approved QC Specification', index=True,
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

    @api.depends('lot_id', 'lot_id.name')
    def _compute_rm_qc_batch(self):
        for rec in self:
            rec.rm_qc_batch_reference = rec.lot_id.name or ''

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
                raise UserError(_('No QC Manager confirmed specification for this product/stage.'))
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

    def write(self, vals):
        if vals.get('quality_state') == 'pass':
            self._rm_qc_verify_before_pass()
        if {'rm_qc_specification_id', 'rm_qc_parameter_line_ids'}.intersection(vals):
            if any(check.quality_state in ('pass', 'fail') for check in self):
                raise UserError(_('Completed QC check specifications are locked.'))
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
    spec_line_id = fields.Many2one('rm.qc.specification.line', string='Specification Source',
                                  readonly=True)
    name = fields.Char(string='MIC / Property', required=True)
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
    sample_size = fields.Char(string='Sampling Rule', readonly=True)
    samples_to_test = fields.Integer(string='Actual Samples to Test', default=1,
                                     help='Set this using actual pallets/rolls/batch size.')
    measurements_per_sample = fields.Integer(string='Measurements per Sample', default=1,
                                             readonly=True)
    sample_method = fields.Char(string='Sample Method', readonly=True)
    inspection_level = fields.Char(string='Inspection Level', readonly=True)
    inspection_frequency = fields.Char(string='Inspection Frequency', readonly=True)
    log_ids = fields.One2many('rm.qc.inspection.log', 'parameter_id', string='Measurement Logs')

    @api.constrains('samples_to_test')
    def _check_samples(self):
        for rec in self:
            if rec.samples_to_test < 1 or rec.samples_to_test > 1000:
                raise ValidationError(_('Samples to Test must be 1–1000.'))

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

    def write(self, vals):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Completed inspection logs are locked.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.parameter_id.quality_check_id.quality_state in ('pass', 'fail') for rec in self):
            raise UserError(_('Cannot delete a completed inspection log.'))
        return super().unlink()
