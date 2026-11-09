"""Menu integration regression test (Odoo 19, executed with this addon installed)."""

from odoo.tests.common import TransactionCase


class TestQualityMenuIntegration(TransactionCase):

    def test_rm_qc_menus_belong_to_quality_application(self):
        menus = self.env['ir.ui.menu'].with_context(active_test=False)
        root = menus.search([
            ('name', '=', 'Quality'), ('parent_id', '=', False),
        ], limit=1)
        self.assertTrue(root, 'Native Quality application must be installed')
        quality_control = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Quality Control'),
        ], limit=1) or root
        configuration = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Configuration'),
        ], limit=1) or root

        for xmlid in ('menu_rm_qc_spec', 'menu_rm_qc_quality_checks'):
            menu = self.env.ref('quality_rm_spec_sampling.%s' % xmlid)
            self.assertEqual(menu.parent_id, quality_control)
            self.assertTrue(menu.active)
        for xmlid in (
            'menu_rm_qc_parameters',
            'menu_rm_qc_defects',
            'menu_rm_qc_identification',
            'menu_rm_qc_consumables',
        ):
            menu = self.env.ref('quality_rm_spec_sampling.%s' % xmlid)
            self.assertEqual(menu.parent_id, configuration)
            self.assertTrue(menu.active)
        for xmlid in ('menu_rm_qc_root', 'menu_rm_qc_master'):
            self.assertFalse(
                self.env.ref('quality_rm_spec_sampling.%s' % xmlid).active
            )
