"""Keep exactly one RM specification and inspection menu in Quality.

Do NOT replace standard Quality Control Points / Quality Checks actions:
other native apps depend on their original models and action definitions.
Instead hide only the equivalent native navigation entries and place the
custom actions under the Quality app. All core records and actions survive.

For upgrades from 19.0.1.0.14, restore the original native action/name from
the snapshot written by that release before hiding the original menu.
"""
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_SNAPSHOTS = {
    'points': 'quality_rm_spec_sampling.native_control_points_menu',
    'checks': 'quality_rm_spec_sampling.native_quality_checks_menu',
}


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _rm_qc_quality_root(self):
        """Locate the existing Quality app; never assume Enterprise menu IDs."""
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        root = self.env.ref('quality.menu_quality_root', raise_if_not_found=False)
        if root and root._name == 'ir.ui.menu' and root.exists():
            return root
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', ['quality', 'quality_control']),
        ])
        native = menus.browse(data.mapped('res_id')).exists()
        root = native.filtered(lambda m: not m.parent_id and m.name == 'Quality')[:1]
        if root:
            return root
        return menus.search([
            ('parent_id', '=', False), ('name', '=', 'Quality'),
        ], limit=1)

    @api.model
    def _rm_qc_native_menu(self, root, kind):
        """Find the installed standard menu, including one changed by v14."""
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        params = self.env['ir.config_parameter'].sudo()
        raw = params.get_param(_SNAPSHOTS[kind])
        if raw:
            try:
                snapshot = json.loads(raw)
                candidate = menus.browse(snapshot['id']).exists()
                if candidate:
                    return candidate
            except (ValueError, TypeError, KeyError):
                _logger.warning('Invalid RM QC native menu snapshot for %s', kind)

        source_model = 'quality.point' if kind == 'points' else 'quality.check'
        labels = (
            {'Control Points', 'Quality Control Points', 'RM QC Specification'}
            if kind == 'points' else
            {'Quality Checks', 'Quality Check', 'Quality Inspection'}
        )
        ids = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', [
                'quality', 'quality_control', 'quality_mrp',
                'quality_mrp_workorder',
            ]),
        ]).mapped('res_id')
        descendant_ids = set(menus.search([('id', 'child_of', root.id)]).ids)
        available = menus.browse(ids).exists().filtered(
            lambda m: m.active and m.id != root.id
            and m.action and m.action._name == 'ir.actions.act_window'
            and m.action.res_model == source_model
            and m.id in descendant_ids
        )
        if not available:
            return menus.browse()
        control = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Quality Control'),
        ], limit=1)
        return available.sorted(key=lambda m: (
            m.name not in labels,
            m.parent_id.id != (control.id if control else root.id),
            m.id,
        ))[:1]

    @api.model
    def _rm_qc_preserve_and_hide_native(self, root, kind):
        """Restore earlier unsafe action rewires, then hide native menu only."""
        params = self.env['ir.config_parameter'].sudo()
        key = _SNAPSHOTS[kind]
        native = self._rm_qc_native_menu(root, kind)
        if not native:
            _logger.warning('RM QC %s: no native Quality menu found', kind)
            return False
        native = native.sudo().with_context(active_test=False, lang='en_US')
        raw = params.get_param(key)
        if raw:
            try:
                original = json.loads(raw)
            except (ValueError, TypeError):
                _logger.warning('RM QC %s: corrupt snapshot; keeping current action', kind)
                return False
        else:
            action = native.action
            original = {
                'id': native.id, 'name': native.name,
                'action': '%s,%s' % (action._name, action.id) if action else False,
                'active': native.active,
            }
            params.set_param(key, json.dumps(original))
        values = {}
        # Only write when values differ. This also repairs v14 native rewires.
        if native.name != original.get('name') and original.get('name'):
            values['name'] = original['name']
        if original.get('action') is not None:
            action = original['action'] or False
            current = '%s,%s' % (native.action._name, native.action.id) if native.action else False
            if current != action:
                values['action'] = action
        if native.active:
            values['active'] = False
        if values:
            native.write(values)
        return True

    @api.model
    def _rm_qc_place_quality_menus(self):
        """Expose only RM QC screens under Quality; never change core actions."""
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        root = self._rm_qc_quality_root()
        if not root:
            _logger.warning('RM QC menu integration skipped: Quality root missing')
            return False
        control = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Quality Control'),
        ], limit=1) or root
        configuration = menus.search([
            ('parent_id', '=', root.id), ('name', '=', 'Configuration'),
        ], limit=1) or root

        def reposition(short_id, parent, sequence, active=True):
            entry = self.env.ref(
                'quality_rm_spec_sampling.%s' % short_id,
                raise_if_not_found=False,
            )
            if not entry:
                return
            values = {}
            if entry.parent_id != parent:
                values['parent_id'] = parent.id
            if entry.sequence != sequence:
                values['sequence'] = sequence
            if entry.active != active:
                values['active'] = active
            if values:
                entry.sudo().write(values)

        # Hide native menu entries, preserving their actions and all records.
        # If native entry cannot be located, the custom menu is still displayed.
        self._rm_qc_preserve_and_hide_native(root, 'points')
        self._rm_qc_preserve_and_hide_native(root, 'checks')

        reposition('menu_rm_qc_spec', control, 40)
        reposition('menu_rm_qc_quality_checks', control, 45)
        for sequence, short_id in enumerate((
            'menu_rm_qc_parameters', 'menu_rm_qc_defects',
            'menu_rm_qc_identification', 'menu_rm_qc_consumables',
        ), start=80):
            reposition(short_id, configuration, sequence)
        for short_id in ('menu_rm_qc_root', 'menu_rm_qc_master', 'menu_rm_qc_pr'):
            entry = self.env.ref(
                'quality_rm_spec_sampling.%s' % short_id,
                raise_if_not_found=False,
            )
            if entry and entry.active:
                entry.sudo().write({'active': False})
        return True

    @api.model
    def _rm_qc_restore_quality_menus(self):
        """Return native Quality menus to their original state on uninstall."""
        params = self.env['ir.config_parameter'].sudo()
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        for key in _SNAPSHOTS.values():
            raw = params.get_param(key)
            if not raw:
                continue
            try:
                original = json.loads(raw)
                native = menus.browse(original['id']).exists()
                if native:
                    values = {'active': original.get('active', True)}
                    if original.get('name'):
                        values['name'] = original['name']
                    if 'action' in original:
                        values['action'] = original['action'] or False
                    native.write(values)
                params.search([('key', '=', key)]).unlink()
            except (ValueError, TypeError, KeyError):
                _logger.warning('Cannot restore invalid RM QC menu snapshot %s', key)
        return True
