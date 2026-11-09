"""Proposed Odoo 19 staging tests for QC without a TDS approval step."""
from odoo.tests.common import TransactionCase


class TestMasterDrivenQuality(TransactionCase):

    def _film(self, name):
        return self.env['product.template'].create({
            'name': name,
            'purchase_ok': True,
            'rm_qc_required': True,
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        })

    def test_incoming_rules_do_not_require_qcs(self):
        product = self._film('Film without TDS')
        rules = self.env['rm.qc.parameter.template'].applicable_to(
            product.product_variant_id, 'incoming')
        self.assertTrue(rules)
        self.assertFalse(self.env['rm.qc.specification'].search([
            ('product_tmpl_id', '=', product.id),
        ]))
        commands = rules.inspection_commands(product.product_variant_id)
        self.assertEqual(len(commands), len(rules))

    def test_nominal_thickness_resolved_from_product_property(self):
        product = self._film('Film 120 micron')
        prop = product.rm_qc_identification_line_ids.filtered(
            lambda p: p.name == 'Thickness / Gauge')[:1]
        self.assertTrue(prop)
        prop.value = '120'
        thickness = self.env['rm.qc.parameter.template'].applicable_to(
            product.product_variant_id, 'incoming').filtered(
                lambda r: r.name == 'Film Thickness / Caliper')
        self.assertEqual(len(thickness), 1)
        command = thickness.inspection_commands(product.product_variant_id)[0]
        vals = command[2]
        self.assertEqual(vals['limit_mode'], 'numeric')
        self.assertAlmostEqual(vals['lsl_numeric'], 114)
        self.assertAlmostEqual(vals['usl_numeric'], 126)

    def test_without_nominal_formula_remains_manual(self):
        product = self._film('Film nominal missing')
        thickness = self.env['rm.qc.parameter.template'].applicable_to(
            product.product_variant_id, 'incoming').filtered(
                lambda r: r.name == 'Film Thickness / Caliper')
        vals = thickness.inspection_commands(product.product_variant_id)[0][2]
        self.assertEqual(vals['limit_mode'], 'reference')
