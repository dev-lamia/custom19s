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

    def test_activate_directly_without_builtin_qc_approval(self):
        product = self.env['product.template'].create({
            'name': 'RM QC Direct Activate Test',
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        })
        spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': product.id, 'scope': 'incoming',
        })
        self.assertEqual(spec.state, 'draft')
        self.assertTrue(spec.line_ids)
        spec.line_ids.filtered(
            lambda l: l.limit_type in ('pct', 'abs')).write({'target_numeric': 12.0})
        spec.action_approve()  # UI label: Activate Standard; no internal approval.
        self.assertEqual(spec.state, 'approved')
        self.assertEqual(spec.approved_by, self.env.user)
        duplicated = spec.copy()
        self.assertEqual(duplicated.state, 'draft')
        self.assertTrue(duplicated.line_ids)
        self.assertFalse(duplicated.approved_by)

    def test_legacy_submitted_standard_can_be_activated(self):
        product = self.env['product.template'].create({
            'name': 'RM QC Legacy Submitted Test',
            'rm_qc_material_type': 'film',
            'rm_qc_film_type': 'pet',
        })
        spec = self.env['rm.qc.specification'].create({
            'product_tmpl_id': product.id,
            'scope': 'incoming',
        })
        self.assertTrue(spec.line_ids)
        spec.write({'state': 'submitted'})
        spec.line_ids.filtered(
            lambda l: l.limit_type in ('pct', 'abs')).write({'target_numeric': 12.0})
        spec.action_approve()
        self.assertEqual(spec.state, 'approved')
