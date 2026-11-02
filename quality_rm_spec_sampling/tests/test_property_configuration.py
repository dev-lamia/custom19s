from odoo.tests.common import TransactionCase


class TestQcProductPropertyConfiguration(TransactionCase):
    def test_auto_populate_and_preserve_values_on_material_type_switch(self):
        product = self.env['product.template'].create({
            'name': 'Config-driven RM Property Test',
            'rm_qc_material_type': 'film',
        })
        all_lines = self.env['rm.qc.product.identification'].with_context(
            active_test=False)
        film_templates = self.env['rm.qc.identification.template'].search([
            ('material_type', '=', 'film'),
        ])
        film_lines = all_lines.search([
            ('product_tmpl_id', '=', product.id), ('active', '=', True),
        ])
        self.assertEqual(len(film_lines), len(film_templates))
        self.assertTrue(set(film_lines.mapped('name')) == set(film_templates.mapped('name')))
        thickness = film_lines.filtered(lambda x: x.name == 'Thickness / Gauge')
        self.assertEqual(len(thickness), 1)
        thickness.write({'value': '120', 'uom_text': 'µm'})

        product.write({'rm_qc_material_type': 'ink'})
        ink_lines = all_lines.search([
            ('product_tmpl_id', '=', product.id), ('active', '=', True),
        ])
        self.assertTrue(ink_lines)
        self.assertFalse(thickness.active)
        self.assertNotIn('Thickness / Gauge', ink_lines.mapped('name'))

        product.write({'rm_qc_material_type': 'film'})
        self.assertTrue(thickness.active)
        self.assertEqual(thickness.value, '120')
        refreshed = all_lines.search([
            ('product_tmpl_id', '=', product.id), ('active', '=', True),
            ('template_id', '=', thickness.template_id.id),
        ])
        self.assertEqual(len(refreshed), 1)

    def test_new_master_property_syncs_to_existing_products(self):
        product = self.env['product.template'].create({
            'name': 'Configuration Propagation Test',
            'rm_qc_material_type': 'film',
        })
        template = self.env['rm.qc.identification.template'].create({
            'material_type': 'film',
            'name': 'Configuration Test Property',
            'uom_text': 'mm',
        })
        lines = self.env['rm.qc.product.identification'].search([
            ('product_tmpl_id', '=', product.id),
            ('template_id', '=', template.id),
        ])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.uom_text, 'mm')
        template.write({'active': False})
        self.assertFalse(lines.active)
