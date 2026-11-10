"""19.0.1.0.17-18: limit types, catalog errors per test, auto pass, mandatory lot
batches and the receipt validation gate (Odoo 19 runtime tests)."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from ..models.limits import guess_limits


class TestLimitHelpers(TransactionCase):

    def test_workbook_text_is_translated(self):
        pct = guess_limits('Nominal - 5%', 'Nominal', 'Nominal + 5%')
        self.assertEqual((pct['limit_type'], pct['tolerance_pct']), ('pct', '5'))
        absolute = guess_limits('-0.5', 'Nominal', '+0.5')
        self.assertEqual((absolute['limit_type'], absolute['tolerance_abs']), ('abs', 0.5))
        fixed = guess_limits('38', '42', '46')
        self.assertEqual((fixed['limit_type'], fixed['lsl_numeric'], fixed['usl_numeric']),
                         ('minmax', 38.0, 46.0))
        minimum = guess_limits('0.8', '1.2', 'N/A')
        self.assertEqual((minimum['limit_type'], minimum['lsl_numeric']), ('min', 0.8))
        self.assertEqual(guess_limits('Free', 'Free', 'Trace')['limit_type'], 'reference')
        self.assertEqual(guess_limits('9.5 / 3.0', '10.0 / 4.0', '11.0 / N/A')['limit_type'],
                         'reference')


class TestRmQcReceiptFlow(TransactionCase):

    def setUp(self):
        super().setUp()
        self.picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('company_id', '=', self.env.company.id),
        ], limit=1)
        self.product = self.env['product.template'].create({
            'name': 'PET 12 mic 560mm (test)',
            'rm_qc_required': True,
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        }).product_variant_id
        self.spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id, 'scope': 'incoming',
        })
        self.thickness = self.spec.line_ids.filtered(
            lambda l: l.name == 'Film Thickness / Caliper')

    def _activate(self):
        self.spec.line_ids.filtered(
            lambda l: l.limit_type in ('pct', 'abs')).write({'target_numeric': 12.0})
        self.spec.action_approve()

    def _receipt(self, product=None, lot_name='PET-B001'):
        product = product or self.product
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type.id,
            'location_id': (self.picking_type.default_location_src_id.id
                            or self.env.ref('stock.stock_location_suppliers').id),
            'location_dest_id': (self.picking_type.default_location_dest_id.id
                                 or self.env.ref('stock.stock_location_stock').id),
        })
        self.env['stock.move'].create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })
        if lot_name:
            picking.action_confirm()
            move = picking.move_ids
            move.move_line_ids.unlink()
            self.env['stock.move.line'].create({
                'move_id': move.id, 'picking_id': picking.id,
                'product_id': product.id, 'product_uom_id': product.uom_id.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'lot_name': lot_name, 'quantity': 1.0,
            })
        return picking

    @staticmethod
    def _good_value(parameter):
        if parameter.limit_type == 'min':
            return str(parameter.lsl_numeric)
        if parameter.limit_type == 'max':
            return str(parameter.usl_numeric)
        return str((parameter.lsl_numeric + parameter.usl_numeric) / 2.0)

    def _fill_all_good(self, check):
        for parameter in check.rm_qc_parameter_line_ids:
            for log in parameter.log_ids:
                if parameter.limit_type == 'reference':
                    log.write({'value_text': 'OK', 'manual_result': 'pass'})
                else:
                    log.write({'value_text': self._good_value(parameter)})

    # -- TDS -------------------------------------------------------------
    def test_target_fills_min_max(self):
        self.assertEqual(self.thickness.limit_type, 'pct')
        self.assertEqual(self.thickness.tolerance_pct, '5')
        self.thickness.target_numeric = 12.0
        self.assertAlmostEqual(self.thickness.lsl_numeric, 11.4)
        self.assertAlmostEqual(self.thickness.usl_numeric, 12.6)
        self.thickness.tolerance_pct = '10'
        self.assertAlmostEqual(self.thickness.lsl_numeric, 10.8)

    def test_activation_needs_target(self):
        with self.assertRaises(UserError):
            self.spec.action_approve()

    def test_thickness_has_unit_and_catalog(self):
        self.assertEqual(self.thickness.uom_id.name, 'µm (Micron)')
        self.assertEqual(self.thickness.defect_ids.mapped('code'), ['RM001'])

    # -- Inspection ------------------------------------------------------
    def test_out_of_spec_needs_matching_catalog_error(self):
        self._activate()
        picking = self._receipt()
        picking.action_rm_qc_create_checks()
        check = picking.rm_qc_check_ids.filtered('rm_qc_specification_id')
        parameter = check.rm_qc_parameter_line_ids.filtered(
            lambda p: p.name == 'Film Thickness / Caliper')
        log = parameter.log_ids[:1]
        with self.assertRaises(ValidationError):
            log.write({'value_text': '13.5'})
        rm005 = self.env['rm.qc.defect'].search([('code', '=', 'RM005')])
        with self.assertRaises(ValidationError):
            log.write({'value_text': '13.5', 'defect_id': rm005.id})
        rm001 = self.env['rm.qc.defect'].search([('code', '=', 'RM001')])
        log.write({'value_text': '13.5', 'defect_id': rm001.id})
        self.assertEqual(log.result, 'out_of_spec')
        self.assertEqual(log.allowed_defect_ids, rm001)

    def test_all_readings_ok_passes_automatically(self):
        self._activate()
        picking = self._receipt()
        picking.action_rm_qc_create_checks()
        check = picking.rm_qc_check_ids.filtered('rm_qc_specification_id')
        self.assertEqual(picking.rm_qc_state, 'in_progress')
        self._fill_all_good(check)
        self.assertEqual(check.quality_state, 'pass')
        self.assertEqual(picking.rm_qc_state, 'pass')

    # -- Receipt gate ----------------------------------------------------
    def test_pending_list_status(self):
        self._activate()
        picking = self._receipt()
        self.assertEqual(picking.rm_qc_state, 'pending')

    def test_unfinished_qc_blocks_validation_and_creates_check(self):
        self._activate()
        picking = self._receipt()
        result = picking.button_validate()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('tag'), 'display_notification')
        self.assertNotEqual(picking.state, 'done')
        self.assertTrue(picking.rm_qc_check_ids.filtered('rm_qc_specification_id'))

    def test_failed_qc_blocks_validation(self):
        self._activate()
        picking = self._receipt()
        picking.action_rm_qc_create_checks()
        check = picking.rm_qc_check_ids.filtered('rm_qc_specification_id')
        check.do_fail()
        self.assertEqual(picking.rm_qc_state, 'fail')
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_qc_required_product_is_lot_tracked(self):
        self.assertEqual(self.product.tracking, 'lot')
        with self.assertRaises(ValidationError):
            self.product.product_tmpl_id.tracking = 'none'

    def test_missing_lot_number_blocks_qc(self):
        self._activate()
        picking = self._receipt(lot_name=False)
        self.assertEqual(picking.rm_qc_state, 'no_lot')
        with self.assertRaises(UserError):
            picking.action_rm_qc_create_checks()

    def test_typed_lot_number_becomes_batch_inspection(self):
        self._activate()
        picking = self._receipt(lot_name='PET-B001')
        self.assertEqual(picking.rm_qc_state, 'pending')
        picking.action_rm_qc_create_checks()
        check = picking.rm_qc_check_ids.filtered('rm_qc_specification_id')
        self.assertEqual(len(check), 1)
        self.assertEqual(check.lot_ids.mapped('name'), ['PET-B001'])
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, check.lot_ids)
        # Running it again does not create a second inspection.
        picking.action_rm_qc_create_checks()
        self.assertEqual(len(picking.rm_qc_check_ids.filtered('rm_qc_specification_id')), 1)

    def test_counts_pass_out_of_spec_fail(self):
        self._activate()
        picking = self._receipt()
        picking.action_rm_qc_create_checks()
        check = picking.rm_qc_check_ids.filtered('rm_qc_specification_id')
        thickness = check.rm_qc_parameter_line_ids.filtered(
            lambda p: p.name == 'Film Thickness / Caliper')
        rm001 = self.env['rm.qc.defect'].search([('code', '=', 'RM001')])
        logs = thickness.log_ids
        logs[0].write({'value_text': '12.0'})
        logs[1].write({'value_text': '13.5', 'defect_id': rm001.id})
        self.assertEqual(thickness.pass_count, 1)
        self.assertEqual(thickness.oos_count, 1)
        self.assertEqual(thickness.pending_count, thickness.reading_total - 2)
        self.assertEqual(thickness.test_result, 'fail')
        self.assertEqual(check.rm_qc_pass_count, 1)
        self.assertEqual(check.rm_qc_oos_count, 1)
        self.assertEqual(check.rm_qc_test_fail_count, 1)
        self.assertEqual(picking.rm_qc_oos_count, 1)
        analysis = self.env['rm.qc.inspection.log'].search([
            ('picking_id', '=', picking.id), ('result', '=', 'out_of_spec')])
        self.assertEqual(analysis.batch_reference, 'PET-B001')
        self.assertEqual(analysis.test_name, 'Film Thickness / Caliper')
