"""Native Quality navigation isolation tests (run inside Odoo 19)."""
from odoo.tests.common import TransactionCase


class TestQualityMenusSafe(TransactionCase):

    def test_one_entry_for_each_workflow(self):
        menus = self.env['ir.ui.menu'].with_context(active_test=False)
        root = menus._rm_qc_quality_root()
        self.assertTrue(root)
        visible = menus.search([('id', 'child_of', root.id), ('active', '=', True)])
        spec_action = self.env.ref('quality_rm_spec_sampling.action_rm_qc_spec')
        check_action = self.env.ref('quality_rm_spec_sampling.action_rm_qc_detailed_check')
        self.assertEqual(len(visible.filtered(lambda m: m.action == spec_action)), 1)
        self.assertEqual(len(visible.filtered(lambda m: m.action == check_action)), 1)
        self.assertEqual(
            visible.filtered(lambda m: m.action == spec_action).name,
            'RM QC Specification',
        )
        self.assertEqual(
            visible.filtered(lambda m: m.action == check_action).name,
            'Quality Inspection',
        )
        self.assertFalse(self.env.ref('quality_rm_spec_sampling.menu_rm_qc_root').active)

    def test_native_actions_remain_original_and_menu_is_hidden(self):
        menus = self.env['ir.ui.menu'].with_context(active_test=False)
        params = self.env['ir.config_parameter'].sudo()
        root = menus._rm_qc_quality_root()
        for kind, expected in [('points', 'quality.point'), ('checks', 'quality.check')]:
            native = menus._rm_qc_native_menu(root, kind)
            if native:
                self.assertFalse(native.active)
                self.assertEqual(native.action.res_model, expected)
        before = [params.get_param(k) for k in (
            'quality_rm_spec_sampling.native_control_points_menu',
            'quality_rm_spec_sampling.native_quality_checks_menu',
        )]
        menus._rm_qc_place_quality_menus()
        after = [params.get_param(k) for k in (
            'quality_rm_spec_sampling.native_control_points_menu',
            'quality_rm_spec_sampling.native_quality_checks_menu',
        )]
        self.assertEqual(before, after)
