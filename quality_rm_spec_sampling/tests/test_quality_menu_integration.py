"""Odoo 19 integration tests for native Quality navigation (requires Odoo DB)."""

from odoo.tests.common import TransactionCase


class TestQualityMenuIntegration(TransactionCase):

    def test_native_quality_menus_reused_without_duplicates(self):
        menu_model = self.env['ir.ui.menu'].with_context(
            active_test=False, lang='en_US'
        )
        root = menu_model._rm_qc_quality_root()
        self.assertTrue(root, 'Installed Quality app root must be present')

        spec_action = self.env.ref('quality_rm_spec_sampling.action_rm_qc_spec')
        inspection_action = self.env.ref(
            'quality_rm_spec_sampling.action_rm_qc_detailed_check'
        )
        self.assertEqual(spec_action.res_model, 'rm.qc.specification')
        self.assertEqual(inspection_action.res_model, 'quality.check')
        self.assertEqual(inspection_action.domain, '[]')

        quality_menus = menu_model.search([('id', 'child_of', root.id)])
        spec_menus = quality_menus.filtered(
            lambda item: item.active and item.action == spec_action
        )
        inspection_menus = quality_menus.filtered(
            lambda item: item.active and item.action == inspection_action
        )
        self.assertEqual(len(spec_menus), 1, 'Expected one specification menu')
        self.assertEqual(len(inspection_menus), 1, 'Expected one inspection menu')
        self.assertEqual(spec_menus.name, 'RM QC Specification')
        self.assertEqual(inspection_menus.name, 'Quality Inspection')

        for short_id in ('menu_rm_qc_root', 'menu_rm_qc_master', 'menu_rm_qc_pr'):
            self.assertFalse(
                self.env.ref('quality_rm_spec_sampling.%s' % short_id).active
            )

    def test_configuration_and_upgrade_are_idempotent(self):
        menu_model = self.env['ir.ui.menu']
        root = menu_model._rm_qc_quality_root()
        configuration = menu_model.with_context(active_test=False).search([
            ('parent_id', '=', root.id), ('name', '=', 'Configuration'),
        ], limit=1) or root

        for short_id in (
            'menu_rm_qc_parameters', 'menu_rm_qc_defects',
            'menu_rm_qc_identification', 'menu_rm_qc_consumables',
        ):
            menu = self.env.ref('quality_rm_spec_sampling.%s' % short_id)
            self.assertEqual(menu.parent_id, configuration)
            self.assertTrue(menu.active)

        params = self.env['ir.config_parameter'].sudo()
        before_points = params.get_param(
            'quality_rm_spec_sampling.native_control_points_menu'
        )
        before_checks = params.get_param(
            'quality_rm_spec_sampling.native_quality_checks_menu'
        )
        menu_model._rm_qc_place_quality_menus()
        self.assertEqual(params.get_param(
            'quality_rm_spec_sampling.native_control_points_menu'
        ), before_points)
        self.assertEqual(params.get_param(
            'quality_rm_spec_sampling.native_quality_checks_menu'
        ), before_checks)

    def test_native_quality_point_model_is_not_replaced(self):
        # The business object remains a native automatic-check rule.
        self.assertIn('quality.point', self.env)
        self.assertIn('rm.qc.specification', self.env)
        self.assertEqual(self.env['rm.qc.specification']._name,
                         'rm.qc.specification')
