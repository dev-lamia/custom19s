"""Non-destructive integration of RM QC menus into native Quality navigation.

The native quality.point and quality.check models and their actions remain
unchanged. Only native menu visibility is toggled after replacement menus
are safely attached; prior v14 action rewires are reversed from snapshots.
The integration is best-effort so an Enterprise menu layout difference cannot
abort a module upgrade or prevent Odoo from starting.
"""

import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_SNAPSHOT_KEYS = {
    'points': 'quality_rm_spec_sampling.native_control_points_menu',
    'checks': 'quality_rm_spec_sampling.native_quality_checks_menu',
}
_NATIVE_MODELS = {'points': 'quality.point', 'checks': 'quality.check'}
_NATIVE_LABELS = {
    'points': {'Control Points', 'Quality Control Points', 'RM QC Specification'},
    'checks': {'Quality Checks', 'Quality Check', 'Quality Inspection'},
}


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _rm_qc_menu(self, short_id):
        menu = self.env.ref(
            'quality_rm_spec_sampling.%s' % short_id,
            raise_if_not_found=False,
        )
        return menu if menu and menu._name == 'ir.ui.menu' and menu.exists() else self.browse()

    @api.model
    def _rm_qc_quality_root(self):
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        menu = self.env.ref('quality.menu_quality_root', raise_if_not_found=False)
        if menu and menu._name == 'ir.ui.menu' and menu.exists():
            return menu.sudo()
        external_ids = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', ['quality', 'quality_control']),
        ])
        candidates = menus.browse(external_ids.mapped('res_id')).exists()
        root = candidates.filtered(lambda m: not m.parent_id and m.name == 'Quality')[:1]
        if root:
            return root
        return menus.search([('parent_id', '=', False), ('name', '=', 'Quality')], limit=1)

    @api.model
    def _rm_qc_find_native(self, root, kind, snapshot=None):
        """Only select Quality-owned menus, never unrelated custom menus."""
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        if snapshot:
            try:
                saved_id = int(snapshot['id'])
            except (KeyError, TypeError, ValueError):
                saved_id = 0
            if saved_id:
                found = menus.browse(saved_id).exists()
                own = self._rm_qc_menu('menu_rm_qc_spec') | self._rm_qc_menu('menu_rm_qc_quality_checks')
                if found and found not in own and found.id != root.id:
                    # A snapshot references the specific menu edited by 19.0.1.0.14.
                    return found

        refs = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('module', 'in', ['quality', 'quality_control', 'quality_mrp',
                             'quality_mrp_workorder']),
        ])
        if not refs:
            return menus.browse()
        descendants = set(menus.search([('id', 'child_of', root.id)]).ids)
        candidates = menus.browse(refs.mapped('res_id')).exists().filtered(
            lambda m: m.id != root.id and m.id in descendants
            and m.name in _NATIVE_LABELS[kind]
            and m.action and m.action._name == 'ir.actions.act_window'
            and m.action.res_model == _NATIVE_MODELS[kind]
        )
        if not candidates:
            return menus.browse()
        return candidates.sorted(key=lambda m: m.id)[:1]

    @api.model
    def _rm_qc_place_quality_menus(self):
        """Upgrade-safe placement. Never let a menu customization block boot."""
        try:
            with self.env.cr.savepoint():
                return self._rm_qc_place_quality_menus_inner()
        except Exception:
            _logger.exception(
                'RM QC menu integration was skipped; standard Quality and RM QC '
                'data are unchanged. The standalone RM Quality navigation remains available.'
            )
            # XML leaves the own menu root active until integration succeeds.
            return False

    @api.model
    def _rm_qc_place_quality_menus_inner(self):
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        quality_root = self._rm_qc_quality_root()
        if not quality_root:
            _logger.warning('RM QC: cannot find native Quality app; keeping existing RM Quality menu.')
            return False
        submenus = menus.search([('parent_id', '=', quality_root.id)])
        control = submenus.filtered(lambda m: m.name == 'Quality Control')[:1] or quality_root
        config = submenus.filtered(lambda m: m.name == 'Configuration')[:1] or quality_root

        def move(short_id, new_parent, position):
            menu = self._rm_qc_menu(short_id)
            if not menu:
                _logger.warning('RM QC: expected menu %s is missing; keeping fallback app', short_id)
                return False
            values = {}
            if menu.parent_id.id != new_parent.id:
                values['parent_id'] = new_parent.id
            if menu.sequence != position:
                values['sequence'] = position
            if not menu.active:
                values['active'] = True
            if values:
                menu.sudo().write(values)
            return True

        items = (
            ('menu_rm_qc_spec', control, 40),
            ('menu_rm_qc_pending', control, 42),
            ('menu_rm_qc_quality_checks', control, 45),
            ('menu_rm_qc_parameters', config, 80),
            ('menu_rm_qc_defects', config, 81),
            ('menu_rm_qc_uom', config, 84),
            ('menu_rm_qc_identification', config, 82),
            ('menu_rm_qc_consumables', config, 83),
        )
        for item in items:
            if not move(*item):
                return False

        # Snapshot restoration and hiding are best effort independently:
        # a native version difference cannot break placement of custom menus.
        for kind in ('points', 'checks'):
            try:
                with self.env.cr.savepoint():
                    self._rm_qc_restore_and_hide_native(quality_root, kind)
            except Exception:
                _logger.exception('RM QC: unable to hide native %s menu; leaving it visible', kind)

        # Only now hide the old root; never hide it when menu placement failed.
        for short_id in ('menu_rm_qc_root', 'menu_rm_qc_master', 'menu_rm_qc_pr'):
            item = self._rm_qc_menu(short_id)
            if item and item.active:
                item.sudo().write({'active': False})
        return True

    @api.model
    def _rm_qc_restore_and_hide_native(self, root, kind):
        params = self.env['ir.config_parameter'].sudo()
        key = _SNAPSHOT_KEYS[kind]
        raw = params.get_param(key)
        snapshot = None
        if raw:
            try:
                candidate = json.loads(raw)
                if isinstance(candidate, dict):
                    snapshot = candidate
            except (ValueError, TypeError):
                _logger.warning('RM QC: invalid native %s menu snapshot; do not change this menu', kind)
                return False
        native = self._rm_qc_find_native(root, kind, snapshot)
        if not native:
            _logger.info('RM QC: native %s menu not located; leaving all native menus untouched', kind)
            return False
        native = native.sudo().with_context(active_test=False, lang='en_US')
        if snapshot is None:
            action = native.action
            snapshot = {
                'id': native.id,
                'name': native.name,
                'action': '%s,%s' % (action._name, action.id) if action else False,
                'active': native.active,
            }
            params.set_param(key, json.dumps(snapshot))
        elif int(snapshot.get('id', 0)) != native.id:
            _logger.warning('RM QC: mismatched %s snapshot; native menu remains unchanged', kind)
            return False

        custom_action_id = (
            'action_rm_qc_spec' if kind == 'points' else 'action_rm_qc_detailed_check'
        )
        custom_action = self.env.ref(
            'quality_rm_spec_sampling.%s' % custom_action_id,
            raise_if_not_found=False,
        )
        updates = {}
        if custom_action and native.action == custom_action:
            if 'action' in snapshot:
                updates['action'] = snapshot.get('action') or False
            if snapshot.get('name'):
                updates['name'] = snapshot['name']
        if native.active:
            updates['active'] = False
        if updates:
            native.write(updates)
        return True

    @api.model
    def _rm_qc_restore_quality_menus(self):
        """Return original native menu visibility/action on addon uninstall."""
        parameters = self.env['ir.config_parameter'].sudo()
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        for kind, key in _SNAPSHOT_KEYS.items():
            raw = parameters.get_param(key)
            if not raw:
                continue
            try:
                with self.env.cr.savepoint():
                    original = json.loads(raw)
                    native = menus.browse(int(original['id'])).exists()
                    if native:
                        update = {'active': original.get('active', True)}
                        current_action = native.action
                        expected_action = self.env.ref(
                            'quality_rm_spec_sampling.%s' % (
                                'action_rm_qc_spec' if kind == 'points'
                                else 'action_rm_qc_detailed_check'),
                            raise_if_not_found=False,
                        )
                        # Never overwrite unrelated user action customizations.
                        if expected_action and current_action == expected_action:
                            update['action'] = original.get('action') or False
                            update['name'] = original.get('name') or native.name
                        native.write(update)
                    parameters.search([('key', '=', key)]).unlink()
            except Exception:
                _logger.exception('RM QC: cannot restore native %s menu on uninstall', kind)
        return True
