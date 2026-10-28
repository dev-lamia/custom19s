from odoo.tests.common import TransactionCase


class TestRmQcSimpleSpecification(TransactionCase):
    def test_incoming_draft_autofills_from_product(self):
        product = self.env['product.template'].create({
            'name': 'RM QC Test Film',
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        })
        spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': product.id,
            'scope': 'incoming',
        })
        self.assertTrue(spec.line_ids, 'Expected predefined film tests')
        self.assertEqual(spec.state, 'draft')

    def test_duplicate_cannot_be_approved_automatically(self):
        product = self.env['product.template'].create({
            'name': 'RM QC Duplicate Test',
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        })
        spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': product.id,
            'scope': 'incoming',
        })
        spec.action_submit()
        spec.action_approve()
        duplicated = spec.copy()
        self.assertEqual(duplicated.state, 'draft')
        self.assertTrue(duplicated.line_ids)
        self.assertFalse(duplicated.approved_by)
