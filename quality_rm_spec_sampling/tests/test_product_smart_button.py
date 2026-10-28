from odoo.tests.common import TransactionCase


class TestProductQcSmartButton(TransactionCase):
    def test_product_linked_specs_and_action(self):
        product = self.env['product.template'].create({
            'name': 'Linked RM QC Smart Button Test',
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
            'rm_qc_required': True,
        })
        self.assertEqual(product.rm_qc_specification_count, 0)
        specification = self.env['rm.qc.specification'].create({
            'product_tmpl_id': product.id,
            'scope': 'incoming',
        })
        product.invalidate_recordset(['rm_qc_specification_count'])
        self.assertEqual(product.rm_qc_specification_count, 1)
        action = product.action_rm_qc_view_specifications()
        self.assertEqual(action['res_model'], 'rm.qc.specification')
        self.assertEqual(action['domain'], [('product_tmpl_id', '=', product.id)])
        self.assertEqual(action['context']['default_product_tmpl_id'], product.id)
        self.assertEqual(action['context']['default_scope'], 'incoming')
        self.assertEqual(action['view_mode'], 'list,form')
        specification.action_archive_spec() if specification.state == 'approved' else specification.write({'active': False})
        product.invalidate_recordset(['rm_qc_specification_count'])
        self.assertEqual(product.rm_qc_specification_count, 1)
        self.assertFalse(self.env['rm.qc.specification'].search(action['domain']))
        self.assertTrue(self.env['rm.qc.specification'].with_context(active_test=False).search(action['domain']))
