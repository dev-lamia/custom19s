"""Regression coverage for receipt/product/lot QC deduplication (Odoo 19)."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestNoDuplicateReceiptQC(TransactionCase):

    def setUp(self):
        super().setUp()
        self.picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        self.assertTrue(self.picking_type, 'An incoming picking type is required')

        self.product = self.env['product.template'].create({
            'name': 'QC Dedup Incoming PET',
            'rm_qc_required': True,
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        }).product_variant_id
        self.spec = self._make_active_specification()
        self.test_type = self.env['quality.point.test_type'].search([
            ('technical_name', '=', 'passfail'),
        ], limit=1)
        self.assertTrue(self.test_type)
        self.picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type.id,
            'location_id': (self.picking_type.default_location_src_id.id
                            or self.env.ref('stock.stock_location_suppliers').id),
            'location_dest_id': (self.picking_type.default_location_dest_id.id
                                 or self.env.ref('stock.stock_location_stock').id),
        })
        self.env['stock.move'].create({
            'name': self.product.display_name,
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product.uom_id.id,
            'picking_id': self.picking.id,
            'location_id': self.picking.location_id.id,
            'location_dest_id': self.picking.location_dest_id.id,
        })

    def _make_active_specification(self):
        spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'scope': 'incoming',
        })
        self.assertTrue(spec.line_ids)
        spec.line_ids.filtered(
            lambda l: l.limit_type in ('pct', 'abs')).write({'target_numeric': 12.0})
        spec.action_approve()
        return spec

    def _matching_checks(self):
        return self.env['quality.check'].search([
            ('picking_id', '=', self.picking.id),
            ('product_id', '=', self.product.id),
            ('lot_ids', '=', False),
        ])

    def test_repeat_button_reuses_existing_check(self):
        self.picking.action_rm_qc_create_checks()
        check = self._matching_checks()
        self.assertEqual(len(check), 1)
        self.assertEqual(check.rm_qc_specification_id, self.spec)
        self.assertTrue(check.rm_qc_parameter_line_ids)
        self.picking.action_rm_qc_create_checks()
        self.assertEqual(self._matching_checks(), check)

    def test_new_standard_keeps_original_inspection(self):
        self.picking.action_rm_qc_create_checks()
        check = self._matching_checks()
        self._make_active_specification()  # A newer approved TDS is available.
        self.picking.action_rm_qc_create_checks()
        self.assertEqual(self._matching_checks(), check)
        self.assertEqual(check.rm_qc_specification_id, self.spec)

    def test_manual_second_rm_inspection_is_rejected(self):
        self.picking.action_rm_qc_create_checks()
        with self.assertRaises(ValidationError):
            self.env['quality.check'].create({
                'title': 'Duplicate',
                'product_id': self.product.id,
                'picking_id': self.picking.id,
                'test_type_id': self.test_type.id,
                'measure_on': 'product',
                'rm_qc_scope': 'incoming',
                'rm_qc_specification_id': self.spec.id,
                'company_id': self.env.company.id,
            })
        self.assertEqual(len(self._matching_checks()), 1)

    def test_existing_native_draft_check_gets_qc_standard(self):
        native_check = self.env['quality.check'].create({
            'title': 'Native pending inspection',
            'product_id': self.product.id,
            'picking_id': self.picking.id,
            'test_type_id': self.test_type.id,
            'measure_on': 'product',
            'company_id': self.env.company.id,
        })
        self.picking.action_rm_qc_create_checks()
        self.assertEqual(self._matching_checks(), native_check)
        self.assertEqual(native_check.rm_qc_specification_id, self.spec)
        self.assertTrue(native_check.rm_qc_parameter_line_ids)
