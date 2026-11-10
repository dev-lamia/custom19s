"""Quality navigation and menu safety regression tests (Odoo 19 runtime)."""
from odoo.tests.common import TransactionCase


class TestQualityMenusSafe(TransactionCase):
    def test_custom_entries_visible_under_quality(self):
        menus = self.env['ir.ui.menu'].with_context(active_test=False)
        root = menus._rm_qc_quality_root()
        self.assertTrue(root)
        menus._rm_qc_place_quality_menus()
        qroot = self.env.ref('quality_rm_spec_sampling.menu_rm_qc_root')
        spec = self.env.ref('quality_rm_spec_sampling.menu_rm_qc_spec')
        check = self.env.ref('quality_rm_spec_sampling.menu_rm_qc_quality_checks')
        self.assertTrue(spec.active)
        self.assertTrue(check.active)
        self.assertEqual(spec.action.res_model, 'rm.qc.specification')
        self.assertEqual(check.action.res_model, 'quality.check')
        if not qroot.active:
            self.assertIn(root.id, menus.search([('id', 'parent_of', spec.id)]).ids)
            self.assertIn(root.id, menus.search([('id', 'parent_of', check.id)]).ids)

    def test_quality_menu_integration_idempotent(self):
        menus = self.env['ir.ui.menu']
        self.assertTrue(menus._rm_qc_place_quality_menus())
        spec = self.env.ref('quality_rm_spec_sampling.menu_rm_qc_spec')
        check = self.env.ref('quality_rm_spec_sampling.menu_rm_qc_quality_checks')
        before = (spec.parent_id.id, spec.action.id, check.parent_id.id, check.action.id)
        self.assertTrue(menus._rm_qc_place_quality_menus())
        after = (spec.parent_id.id, spec.action.id, check.parent_id.id, check.action.id)
        self.assertEqual(before, after)
