"""Reuse Odoo Quality's existing menus without duplicating work screens.

The core ``quality.point`` model is not interchangeable with a TDS: a QCP
is an automatic check-generation rule, while ``rm.qc.specification`` stores
versioned product tests and sampling limits.  We change the *menu action*,
not either core model, and preserve the original action for uninstall.
"""

import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_MENU_SNAPSHOTS = {
    'points': 'quality_rm_spec_sampling.native_control_points_menu',
    'checks': 'quality_rm_spec_sampling.native_quality_checks_menu',
}


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _rm_qc_quality_root(self):
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        root = self.env.ref('quality.menu_quality_root', raise_if_not_found=False)
        if root and root._name == 'ir.ui.menu':
            return root

        # Some Enterprise editions install the root from quality_control.
        native_refs = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', ['quality', 'quality_control']),
        ])
        native = menus.browse(native_refs.mapped('res_id')).exists()
        root = native.filtered(
            lambda m: not m.parent_id and m.name == 'Quality'
        )[:1]
        return root or menus.search([
            ('parent_id', '=', False), ('name', '=', 'Quality'),
        ], limit=1)

    @api.model
    def _rm_qc_find_native_menu(self, root, source_model, destination_model,
                                known_labels):
        """Find native Quality's primary menu, including after our own upgrade.

        Do not depend on an unverified Enterprise menu XML ID. Also do not
        accidentally rewire menu items installed by this add-on.
        """
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        native_ids = set(self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', [
                'quality', 'quality_control', 'quality_mrp',
                'quality_mrp_workorder',
            ]),
        ]).mapped('res_id'))
        own_ids = set(self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', '=', 'quality_rm_spec_sampling'),
        ]).mapped('res_id'))

        quality_menus = menus.search([('id', 'child_of', root.id)])
        candidates = quality_menus.filtered(
            lambda m: m.active and m.id not in own_ids
            and m.action and m.action._name == 'ir.actions.act_window'
            and m.action.res_model in (source_model, destination_model)
            and (m.id in native_ids or m.name in known_labels)
        )
        if not candidates:
            return menus.browse()

        control = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Quality Control'),
        ], limit=1)
        # Prefer the native top-level Control Points/Quality Checks entry.
        return candidates.sorted(key=lambda m: (
            m.id not in native_ids,
            m.name not in known_labels,
            m.parent_id.id != (control.id if control else root.id),
            m.id,
        ))[:1]

    @api.model
    def _rm_qc_capture_menu_before_rewire(self, menu, kind):
        parameters = self.env['ir.config_parameter'].sudo()
        key = _MENU_SNAPSHOTS[kind]
        if parameters.get_param(key):
            return
        action = menu.action
        parameters.set_param(key, json.dumps({
            'id': menu.id,
            'name': menu.name,
            'action': '%s,%s' % (action._name, action.id) if action else False,
        }))

    @api.model
    def _rm_qc_place_quality_menus(self):
        """Use native Quality navigation and preserve configuration entries.

        Idempotent for install, upgrade and repeated upgrade. Original
        Control Points and Quality Checks actions are captured before update.
        """
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        root = self._rm_qc_quality_root()
        if not root:
            _logger.warning('RM QC integration skipped: Quality root not found.')
            return False

        control = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Quality Control'),
        ], limit=1) or root
        configuration = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Configuration'),
        ], limit=1) or root

        def xml_menu(short_id):
            return self.env.ref(
                'quality_rm_spec_sampling.%s' % short_id,
                raise_if_not_found=False,
            )

        def place(short_id, parent, sequence, active=True):
            menu = xml_menu(short_id)
            if not menu:
                return
            values = {}
            if menu.parent_id != parent:
                values['parent_id'] = parent.id
            if menu.sequence != sequence:
                values['sequence'] = sequence
            if menu.active != active:
                values['active'] = active
            if values:
                menu.sudo().write(values)

        point_menu = self._rm_qc_find_native_menu(
            root, 'quality.point', 'rm.qc.specification',
            {'Control Points', 'Quality Control Points',
             'RM QC Specification', 'RM QC Specifications'},
        )
        check_menu = self._rm_qc_find_native_menu(
            root, 'quality.check', 'quality.check',
            {'Quality Checks', 'Quality Check',
             'Quality Inspection', 'Quality Inspections'},
        )
        spec_action = xml_menu('action_rm_qc_spec')
        inspection_action = xml_menu('action_rm_qc_detailed_check')

        if point_menu and spec_action:
            self._rm_qc_capture_menu_before_rewire(point_menu, 'points')
            point_menu.sudo().write({
                'name': 'RM QC Specification',
                'action': 'ir.actions.act_window,%s' % spec_action.id,
            })
            place('menu_rm_qc_spec', control, 40, active=False)
        else:
            # Customized Quality installs may have no native Control Points
            # entry. Keep exactly one accessible specification menu.
            place('menu_rm_qc_spec', control, 40, active=True)
            _logger.warning('Native Control Points menu not found; using RM QC menu fallback.')

        if check_menu and inspection_action:
            self._rm_qc_capture_menu_before_rewire(check_menu, 'checks')
            check_menu.sudo().write({
                'name': 'Quality Inspection',
                'action': 'ir.actions.act_window,%s' % inspection_action.id,
            })
            place('menu_rm_qc_quality_checks', control, 45, active=False)
        else:
            place('menu_rm_qc_quality_checks', control, 45, active=True)
            _logger.warning('Native Quality Checks menu not found; using RM QC menu fallback.')

        for sequence, short_id in enumerate((
            'menu_rm_qc_parameters',
            'menu_rm_qc_defects',
            'menu_rm_qc_identification',
            'menu_rm_qc_consumables',
        ), start=80):
            place(short_id, configuration, sequence)

        # Keep legacy XML IDs for upgrades, but do not display another app.
        for short_id in ('menu_rm_qc_root', 'menu_rm_qc_master', 'menu_rm_qc_pr'):
            old = xml_menu(short_id)
            if old and old.active:
                old.sudo().write({'active': False})
        return True

    @api.model
    def _rm_qc_restore_quality_menus(self):
        """Return native Quality menu actions when the add-on is uninstalled."""
        parameters = self.env['ir.config_parameter'].sudo()
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        expected_actions = {
            'points': self.env.ref(
                'quality_rm_spec_sampling.action_rm_qc_spec',
                raise_if_not_found=False,
            ),
            'checks': self.env.ref(
                'quality_rm_spec_sampling.action_rm_qc_detailed_check',
                raise_if_not_found=False,
            ),
        }
        for kind, key in _MENU_SNAPSHOTS.items():
            raw = parameters.get_param(key)
            if not raw:
                continue
            try:
                original = json.loads(raw)
            except (TypeError, ValueError):
                _logger.warning('Cannot restore invalid RM QC menu snapshot: %s', key)
                continue
            menu = menus.browse(original.get('id')).exists()
            custom_action = expected_actions[kind]
            if menu and custom_action and menu.action == custom_action:
                values = {'action': original.get('action') or False}
                if menu.name in ('RM QC Specification', 'Quality Inspection'):
                    values['name'] = original.get('name') or menu.name
                menu.write(values)
            parameters.search([('key', '=', key)]).unlink()
        return True
