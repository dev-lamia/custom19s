"""Integrate RM QC navigation in the existing Odoo Quality application."""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _rm_qc_place_quality_menus(self):
        """Reparent existing XML-ID menus on both install and module upgrade.

        The Quality Enterprise menu XML IDs differ between some deployments,
        so locate the installed Quality app instead of referencing an
        undocumented Enterprise XML ID in data XML. Never recreate actions or
        alter inspection, standard, or configuration records.
        """
        menus = self.sudo().with_context(active_test=False, lang='en_US')
        quality_root = self.env.ref('quality.menu_quality_root', raise_if_not_found=False)
        if quality_root and quality_root._name != 'ir.ui.menu':
            quality_root = False
        if not quality_root:
            # Enterprise menu XML IDs vary between deployments. Prefer a
            # native Quality-owned root over any unrelated custom app name.
            xmlids = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'ir.ui.menu'),
                ('module', 'in', ['quality', 'quality_control']),
            ])
            native_menus = menus.browse(xmlids.mapped('res_id')).exists()
            native_roots = native_menus.filtered(lambda item: not item.parent_id)
            quality_root = native_roots.filtered(
                lambda item: item.name == 'Quality'
            )[:1]
        if not quality_root:
            quality_root = menus.search([
                ('parent_id', '=', False), ('name', '=', 'Quality'),
            ], limit=1)
        if not quality_root:
            # An existing installed app must not turn into an unrelated root
            # menu if a nonstandard Quality deployment has no expected menu.
            _logger.warning('RM QC menus not relocated: Quality app menu was not found.')
            return False

        quality_control = menus.search([
            ('parent_id', '=', quality_root.id),
            ('name', '=', 'Quality Control'),
        ], limit=1)
        quality_configuration = menus.search([
            ('parent_id', '=', quality_root.id),
            ('name', '=', 'Configuration'),
        ], limit=1)
        if not quality_control:
            _logger.warning('Quality Control menu not found; placing RM QC work menus directly under Quality.')
        if not quality_configuration:
            _logger.warning('Quality Configuration menu not found; placing RM QC setup menus directly under Quality.')

        def reparent(xmlid, parent, sequence):
            item = self.env.ref(
                'quality_rm_spec_sampling.%s' % xmlid,
                raise_if_not_found=False,
            )
            if not item:
                return
            vals = {}
            if item.parent_id.id != parent.id:
                vals['parent_id'] = parent.id
            if item.sequence != sequence:
                vals['sequence'] = sequence
            if not item.active:
                vals['active'] = True
            if vals:
                item.sudo().write(vals)

        work_parent = quality_control or quality_root
        config_parent = quality_configuration or quality_root
        reparent('menu_rm_qc_spec', work_parent, 40)
        reparent('menu_rm_qc_quality_checks', work_parent, 45)
        for sequence, xmlid in enumerate((
            'menu_rm_qc_parameters',
            'menu_rm_qc_defects',
            'menu_rm_qc_identification',
            'menu_rm_qc_consumables',
        ), start=80):
            reparent(xmlid, config_parent, sequence)

        # The previously installed standalone 'RM Quality' menu must not
        # appear as a second app. Keep both XML IDs for upgrade compatibility.
        for xmlid in ('menu_rm_qc_root', 'menu_rm_qc_master'):
            old_menu = self.env.ref(
                'quality_rm_spec_sampling.%s' % xmlid,
                raise_if_not_found=False,
            )
            if old_menu and old_menu.active:
                old_menu.sudo().write({'active': False})
        return True
