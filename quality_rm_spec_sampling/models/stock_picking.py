from odoo import api, models, fields, _
from odoo.exceptions import UserError

# System parameter: set to 0 to allow validating receipts whose RM QC is not
# finished yet. Failed RM QC always blocks validation.
REQUIRE_QC_PARAM = 'quality_rm_spec_sampling.validate_requires_qc_pass'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rm_qc_check_ids = fields.One2many('quality.check', 'picking_id', string='Quality Checks')
    rm_qc_state = fields.Selection([
        ('none', 'No RM QC'),
        ('pending', 'QC Pending'),
        ('in_progress', 'QC In Progress'),
        ('fail', 'QC Failed'),
        ('pass', 'QC Passed'),
    ], string='RM QC Status', compute='_compute_rm_qc_state', store=True, index=True,
        default='none')

    # ------------------------------------------------------------------
    # What needs inspecting on this receipt
    # ------------------------------------------------------------------
    def _rm_qc_expected_rows(self):
        """[(product, lot_name)] for QC-required products still on the receipt.

        Lots are identified by name so lots typed on a not-yet-validated
        receipt (move line ``lot_name``) are treated the same as real lots.
        """
        self.ensure_one()
        rows = []
        for move in self.move_ids.filtered(
                lambda m: m.state != 'cancel' and m.product_id.rm_qc_required):
            lines = move.move_line_ids.filtered(lambda ml: ml.quantity > 0) or move.move_line_ids
            named = lines.filtered(lambda ml: ml.lot_id or ml.lot_name)
            if named:
                rows.extend((move.product_id, ml.lot_id.name or ml.lot_name) for ml in named)
            elif move.product_uom_qty or lines:
                rows.append((move.product_id, ''))
        seen, unique = set(), []
        for product, lot_name in rows:
            key = (product.id, lot_name or '')
            if key not in seen:
                seen.add(key)
                unique.append((product, lot_name or ''))
        return unique

    def _rm_qc_checks_by_key(self):
        """{(product_id, lot_name): quality.check} for RM incoming inspections."""
        self.ensure_one()
        result = {}
        checks = self.rm_qc_check_ids.filtered(
            lambda c: c.rm_qc_specification_id and c.rm_qc_scope == 'incoming')
        for check in checks.sorted('id'):
            names = check.lot_ids.mapped('name') or ['']
            for name in names:
                result.setdefault((check.product_id.id, name), check)
        return result

    def _rm_qc_relevant_checks(self):
        """RM checks that still match a product/lot present on the receipt."""
        self.ensure_one()
        by_key = self._rm_qc_checks_by_key()
        checks = self.env['quality.check']
        for product, lot_name in self._rm_qc_expected_rows():
            check = by_key.get((product.id, lot_name))
            if check:
                checks |= check
        return checks

    @api.depends('picking_type_id.code', 'state',
                 'move_ids.state', 'move_ids.product_id.rm_qc_required',
                 'move_ids.move_line_ids.lot_id', 'move_ids.move_line_ids.lot_name',
                 'move_ids.move_line_ids.quantity',
                 'rm_qc_check_ids.quality_state', 'rm_qc_check_ids.lot_ids',
                 'rm_qc_check_ids.rm_qc_specification_id')
    def _compute_rm_qc_state(self):
        for picking in self:
            if picking.picking_type_id.code != 'incoming' or picking.state == 'cancel':
                picking.rm_qc_state = 'none'
                continue
            rows = picking._rm_qc_expected_rows()
            if not rows:
                picking.rm_qc_state = 'none'
                continue
            by_key = picking._rm_qc_checks_by_key()
            checks = [by_key.get((product.id, lot_name)) for product, lot_name in rows]
            if any(check and check.quality_state == 'fail' for check in checks):
                picking.rm_qc_state = 'fail'
            elif not all(checks):
                picking.rm_qc_state = 'pending'
            elif all(check.quality_state == 'pass' for check in checks):
                picking.rm_qc_state = 'pass'
            else:
                picking.rm_qc_state = 'in_progress'

    # ------------------------------------------------------------------
    # Create inspections
    # ------------------------------------------------------------------
    def _rm_qc_assign_typed_lots(self):
        """Turn lot numbers typed on the receipt (lot_name) into real lots.

        Odoo normally creates them only at validation; the inspection must be
        batch-wise before that, so create/reuse the same lot record now.
        Validation later uses the assigned lot instead of creating a second one.
        """
        Lot = self.env['stock.lot'].sudo()
        for picking in self:
            lines = picking.move_line_ids.filtered(
                lambda ml: ml.lot_name and not ml.lot_id
                and ml.product_id.rm_qc_required
                and ml.product_id.tracking != 'none')
            for line in lines:
                company = line.company_id or picking.company_id
                lot = Lot.search([
                    ('name', '=', line.lot_name),
                    ('product_id', '=', line.product_id.id),
                    ('company_id', 'in', [company.id, False]),
                ], limit=1)
                if not lot:
                    lot = Lot.create({
                        'name': line.lot_name,
                        'product_id': line.product_id.id,
                        'company_id': company.id,
                    })
                line.sudo().lot_id = lot

    def _rm_qc_ensure_checks(self):
        """Create (or reuse) one RM inspection per receipt x product x lot.

        Never modifies stock quantities and never replaces recorded results.
        """
        QualityCheck = self.env['quality.check']
        test_type = self.env['quality.point.test_type'].search(
            [('technical_name', '=', 'passfail')], limit=1)
        if not test_type:
            raise UserError(_('The standard Pass - Fail Quality test type is missing.'))
        Specification = self.env['rm.qc.specification']
        for picking in self:
            if picking.picking_type_id.code != 'incoming':
                raise UserError(_('RM QC checks can only be generated from incoming receipts.'))
            picking._rm_qc_assign_typed_lots()
            rows = []
            for move in picking.move_ids.filtered(
                    lambda m: m.state != 'cancel' and m.product_id.rm_qc_required):
                lines = move.move_line_ids.filtered(lambda m: m.lot_id)
                if lines:
                    rows.extend([(move.product_id, ml.lot_id) for ml in lines])
                else:
                    rows.append((move.product_id, False))
            seen = set()
            for product, lot in rows:
                key = (product.id, lot.id if lot else False)
                if key in seen:
                    continue
                seen.add(key)
                spec = Specification.with_company(picking.company_id)._find_approved(product)
                if not spec:
                    raise UserError(_('Active QC Standard missing for %s.')
                                    % product.display_name)

                existing_checks = QualityCheck.search([
                    ('picking_id', '=', picking.id),
                    ('product_id', '=', product.id),
                    (('lot_ids', 'in', [lot.id]) if lot else ('lot_ids', '=', False)),
                ], order='id asc')
                if not existing_checks and lot:
                    # An inspection started before the batch number was known:
                    # attach it to this batch instead of creating a duplicate.
                    lotless = QualityCheck.search([
                        ('picking_id', '=', picking.id),
                        ('product_id', '=', product.id),
                        ('lot_ids', '=', False),
                        ('rm_qc_specification_id', '!=', False),
                        ('quality_state', '=', 'none'),
                    ], order='id asc', limit=1)
                    if lotless:
                        lotless.write({'lot_ids': [fields.Command.set([lot.id])]})
                        continue
                if existing_checks:
                    rm_checks = existing_checks.filtered('rm_qc_specification_id')
                    if rm_checks:
                        continue
                    editable = existing_checks.filtered(
                        lambda check: check.quality_state not in ('pass', 'fail')
                        and not check.rm_qc_parameter_line_ids)
                    if editable:
                        check = editable[0]
                        check.write({
                            'rm_qc_scope': 'incoming',
                            'rm_qc_specification_id': spec.id,
                        })
                        check.action_rm_qc_load_specification()
                    else:
                        raise UserError(_(
                            'A completed Quality Check already exists for %(product)s '
                            'on receipt %(receipt)s. A second QC was not created. '
                            'Review the existing check before entering RM samples.'
                        ) % {
                            'product': product.display_name,
                            'receipt': picking.name,
                        })
                    continue

                check = QualityCheck.create({
                    'title': _('RM Incoming QC: %s') % product.display_name,
                    'product_id': product.id, 'picking_id': picking.id,
                    'lot_ids': [fields.Command.set([lot.id])] if lot else [],
                    'test_type_id': test_type.id,
                    'measure_on': 'product',
                    'rm_qc_scope': 'incoming',
                    'rm_qc_specification_id': spec.id,
                    'company_id': picking.company_id.id,
                })
                check.action_rm_qc_load_specification()
        return True

    def _rm_qc_checks_action(self, title=None):
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Incoming RM Quality Checks'),
            'res_model': 'quality.check',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_list').id, 'list'),
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_form').id, 'form'),
            ],
            'domain': [('picking_id', 'in', self.ids), ('rm_qc_specification_id', '!=', False)],
            'context': {'default_rm_qc_scope': 'incoming'},
        }

    def action_rm_qc_create_checks(self):
        """QC Inspection button: works on any receipt, including Done ones."""
        self._rm_qc_ensure_checks()
        return self._rm_qc_checks_action()

    # ------------------------------------------------------------------
    # Validation gate
    # ------------------------------------------------------------------
    def _rm_qc_requires_finished_qc(self):
        value = self.env['ir.config_parameter'].sudo().get_param(REQUIRE_QC_PARAM, '1')
        return str(value).strip().lower() not in ('0', 'false', 'no', 'off')

    def button_validate(self):
        if self.env.context.get('rm_qc_skip_validation_gate'):
            return super().button_validate()
        receipts = self.filtered(
            lambda p: p.picking_type_id.code == 'incoming' and p._rm_qc_expected_rows())
        if receipts:
            # 1) Failed QC (or an out-of-spec reading) always blocks.
            blocked = []
            for picking in receipts:
                for check in picking._rm_qc_relevant_checks():
                    if check.quality_state == 'fail' or (
                            check.quality_state == 'none' and check.rm_qc_failed_count):
                        lots = ', '.join(check.lot_ids.mapped('name')) or _('no batch')
                        blocked.append('%s - %s (%s)' % (
                            picking.name, check.product_id.display_name, lots))
            if blocked:
                raise UserError(_(
                    'RM QC failed, so this receipt cannot be validated:\n%s\n\n'
                    'Remove (or return) the failed batch quantity from the receipt, '
                    'or re-inspect, before validating the rest.'
                ) % '\n'.join(blocked))

            # 2) Inspection must be finished before stock is received.
            if self._rm_qc_requires_finished_qc():
                receipts._rm_qc_ensure_checks()
                unfinished = self.env['quality.check']
                for picking in receipts:
                    unfinished |= picking._rm_qc_relevant_checks().filtered(
                        lambda c: c.quality_state != 'pass')
                if unfinished:
                    next_action = receipts._rm_qc_checks_action(_('Complete RM QC first'))
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('RM QC not finished'),
                            'message': _('%s inspection(s) must pass before this receipt '
                                         'can be validated. Enter the results, then '
                                         'validate again.') % len(unfinished),
                            'type': 'warning',
                            'sticky': False,
                            'next': next_action,
                        },
                    }
        return super().button_validate()
