# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class DynamicReportConfig(models.Model):
    _name = 'dynamic.report.config'
    _description = 'Dynamic Report Configuration'
    _order = 'name'

    name = fields.Char(
        string='Report / Menu Title',
        required=True,
        default='New Report',
        help='Used as the generated menu name and as the printed report title.',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        help='Select the main model for this report.',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Technical Name',
        readonly=True,
    )

    # Kept for backward compatibility with databases created by older versions.
    # New reports use field_line_ids so the user's column order is preserved.
    field_ids = fields.Many2many(
        'ir.model.fields',
        string='Legacy Fields',
        domain="[('model_id', '=', model_id), ('store', '=', True)]",
        help='Legacy field selection retained only for upgrade compatibility.',
    )
    field_line_ids = fields.One2many(
        'dynamic.report.config.field',
        'config_id',
        string='Report Columns',
        copy=True,
    )

    domain_filter = fields.Char(
        string='Domain Filter',
        default='[]',
        help='Use the standard Odoo domain builder to filter report records.',
    )
    limit = fields.Integer(string='Max Records', default=1000)

    enable_date_filter = fields.Boolean(
        string='Enable Date Filter',
        default=False,
        help='Filter report records using a date or datetime field.',
    )
    date_field_id = fields.Many2one(
        'ir.model.fields',
        string='Date Field',
        ondelete='set null',
        help='Choose the date or datetime field used for the report range.',
    )
    date_from = fields.Date(
        string='From Date',
        help='Include records from this date.',
    )
    date_to = fields.Date(
        string='To Date',
        help='Include records through this date.',
    )

    enable_user_filter = fields.Boolean(
        string='Enable User Filter',
        default=False,
        help=(
            'Allow the person running the report to choose a user at print '
            'time instead of forcing the logged-in user.'
        ),
    )
    user_field_id = fields.Many2one(
        'ir.model.fields',
        string='User Field',
        ondelete='set null',
        help=(
            'Choose the stored Many2one field on the report model that points '
            'to Users (res.users), such as Salesperson, Buyer or Responsible User.'
        ),
    )
    group_by_user = fields.Boolean(
        string='Group By User',
        default=False,
        help=(
            'When enabled, the PDF prints a separate table section for each '
            'user. If one user is selected at runtime, only that user section '
            'is printed.'
        ),
    )
    has_user_fields = fields.Boolean(
        string='Has User Fields',
        compute='_compute_has_user_fields',
    )
    active = fields.Boolean(string='Active', default=True)
    subtitle = fields.Char(
        string='Report Subtitle',
        help='Optional subtitle printed below the report title.',
    )
    show_title = fields.Boolean(string='Show Report Title', default=True)
    show_total_records = fields.Boolean(
        string='Show Total Records',
        default=True,
    )
    show_row_number = fields.Boolean(string='Show Row Number', default=True)
    report_title_font_size = fields.Integer(
        string='Report Name Font Size (px)',
        default=18,
        help='Font size used for the report name in the PDF.',
    )
    table_font_size = fields.Integer(
        string='Table Font Size (px)',
        default=9,
        help='Font size used for table headings and table data in the PDF.',
    )
    sort_field_id = fields.Many2one(
        'ir.model.fields',
        string='Sort By',
        ondelete='set null',
        help='Optional main-model field used to order report records.',
    )
    sort_direction = fields.Selection(
        [('asc', 'Ascending'), ('desc', 'Descending')],
        string='Sort Direction',
        default='asc',
        required=True,
    )

    parent_menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Show Menu Under',
        domain="[('action', '=', False)]",
        help='Choose where the generated report menu should appear. Leave '
             'empty to place generated reports under Dynamic Report.',
    )

    menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Generated Menu',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    server_action_id = fields.Many2one(
        'ir.actions.server',
        string='Generated Action',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    print_action_id = fields.Many2one(
        'ir.actions.report',
        string='Print Menu Action',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Makes this report available in the target model Print menu.',
    )

    @api.depends('model_id')
    def _compute_has_user_fields(self):
        model_ids = self.mapped('model_id').ids
        models_with_user_field = set()
        if model_ids:
            user_fields = self.env['ir.model.fields'].sudo().search([
                ('model_id', 'in', model_ids),
                ('ttype', '=', 'many2one'),
                ('relation', '=', 'res.users'),
                ('store', '=', True),
                ('name', 'not in', ['create_uid', 'write_uid']),
            ])
            models_with_user_field = set(user_fields.mapped('model_id').ids)

        for rec in self:
            rec.has_user_fields = bool(
                rec.model_id and rec.model_id.id in models_with_user_field
            )

    @api.constrains('enable_user_filter', 'user_field_id', 'model_id')
    def _check_user_filter_field(self):
        for rec in self:
            if not rec.enable_user_filter:
                continue
            field_rec = rec.user_field_id.sudo()
            if not field_rec:
                raise ValidationError(
                    _('Please select a User Field for the user filter.')
                )
            if (
                field_rec.model_id != rec.model_id
                or field_rec.ttype != 'many2one'
                or field_rec.relation != 'res.users'
                or not field_rec.store
                or field_rec.name in ('create_uid', 'write_uid')
            ):
                raise ValidationError(
                    _(
                        'User Field must be a stored Many2one field on the '
                        'selected model related to Users (res.users).'
                    )
                )

    @api.constrains('report_title_font_size', 'table_font_size')
    def _check_report_font_sizes(self):
        for rec in self:
            if not 10 <= rec.report_title_font_size <= 36:
                raise ValidationError(
                    _('Report Name Font Size must be between 10 and 36 px.')
                )
            if not 6 <= rec.table_font_size <= 18:
                raise ValidationError(
                    _('Table Font Size must be between 6 and 18 px.')
                )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_ids = [(5, 0, 0)]
        self.field_line_ids = [(5, 0, 0)]
        self.sort_field_id = False
        self.date_field_id = False
        self.date_from = False
        self.date_to = False
        self.enable_user_filter = False
        self.user_field_id = False
        self.group_by_user = False

    def action_select_all_fields(self):
        self.ensure_one()
        if not self.model_id:
            raise UserError(_('Please select a model first.'))

        field_records = self.env['ir.model.fields'].sudo().search([
            ('model_id', '=', self.model_id.id),
            ('store', '=', True),
        ], order='field_description, id')

        commands = [(5, 0, 0)]
        sequence = 10
        for field_rec in field_records:
            commands.append((0, 0, {
                'sequence': sequence,
                'field_id': field_rec.id,
            }))
            sequence += 10
        self.field_line_ids = commands
        return True

    def action_add_common_fields(self):
        self.ensure_one()
        if not self.model_id:
            raise UserError(_('Please select a model first.'))

        existing_ids = set(self.field_line_ids.mapped('field_id').ids)
        preferred_names = [
            'name', 'partner_id', 'user_id', 'date_order', 'date',
            'amount_total', 'state', 'company_id',
        ]
        fields_by_name = {
            field.name: field
            for field in self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', self.model_id.id),
                ('name', 'in', preferred_names),
            ])
        }
        sequence = max(self.field_line_ids.mapped('sequence') or [0]) + 10
        vals_list = []
        for field_name in preferred_names:
            field_rec = fields_by_name.get(field_name)
            if not field_rec or field_rec.id in existing_ids:
                continue
            vals_list.append({
                'config_id': self.id,
                'sequence': sequence,
                'field_id': field_rec.id,
            })
            sequence += 10
        if vals_list:
            self.env['dynamic.report.config.field'].create(vals_list)
        return True

    def action_clear_columns(self):
        self.ensure_one()
        self.field_line_ids.unlink()
        self.field_ids = [(5, 0, 0)]
        self._sync_print_action()
        return True

    def action_duplicate_report(self):
        self.ensure_one()
        duplicate = self.copy({
            'name': _('%s (Copy)') % self.name,
            'menu_id': False,
            'server_action_id': False,
            'print_action_id': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicated Report'),
            'res_model': 'dynamic.report.config',
            'res_id': duplicate.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ---------------------------------------------------------------
    # Upgrade compatibility
    # ---------------------------------------------------------------
    def _ensure_field_lines_from_legacy(self):
        """Create ordered column lines for older configs that only had tags."""
        Line = self.env['dynamic.report.config.field']
        for rec in self:
            if rec.field_line_ids or not rec.field_ids:
                continue
            sequence = 10
            vals_list = []
            for field_rec in rec.field_ids.sudo().sorted(
                    key=lambda field: (field.field_description or '', field.id)):
                vals_list.append({
                    'config_id': rec.id,
                    'sequence': sequence,
                    'field_id': field_rec.id,
                })
                sequence += 10
            if vals_list:
                Line.create(vals_list)

    # ---------------------------------------------------------------
    # Menu generation
    # ---------------------------------------------------------------
    def _get_generated_menu_parent(self):
        return self.env.ref('dynamic_report_builder.menu_dynamic_report_root')

    def _sync_menu_and_action(self):
        for rec in self:
            parent = rec.parent_menu_id or rec._get_generated_menu_parent()
            if not rec.menu_id:
                server_action = self.env['ir.actions.server'].sudo().create({
                    'name': rec.name,
                    # Odoo 19 server actions without groups require WRITE
                    # access on the bound model/records. This action is
                    # read-only (it only opens/prints a report), so restrict
                    # it to internal users explicitly and let the report's
                    # normal read ACLs/record rules protect the data.
                    'group_ids': [(6, 0, [
                        self.env.ref('base.group_user').id,
                    ])],
                    'model_id': self.env['ir.model'].sudo()._get_id(
                        'dynamic.report.config'
                    ),
                    'state': 'code',
                    'code': (
                        "action = env['dynamic.report.config'].browse(%d)"
                        ".action_open_generated_report()" % rec.id
                    ),
                })
                menu = self.env['ir.ui.menu'].sudo().create({
                    'name': rec.name,
                    'parent_id': parent.id,
                    'action': 'ir.actions.server,%d' % server_action.id,
                    'sequence': 20,
                })
                rec.write({
                    'menu_id': menu.id,
                    'server_action_id': server_action.id,
                })
            else:
                rec.menu_id.sudo().write({
                    'name': rec.name,
                    'parent_id': parent.id,
                })
                rec.server_action_id.sudo().write({
                    'name': rec.name,
                    'group_ids': [(6, 0, [
                        self.env.ref('base.group_user').id,
                    ])],
                    'code': (
                        "action = env['dynamic.report.config'].browse(%d)"
                        ".action_open_generated_report()" % rec.id
                    ),
                })

    # ---------------------------------------------------------------
    # Unique QWeb template / Print action
    # ---------------------------------------------------------------
    def _get_print_template_xmlid(self):
        self.ensure_one()
        return (
            'dynamic_report_builder.report_dynamic_selected_config_%s'
            % self.id
        )

    def _get_print_template_arch(self):
        self.ensure_one()
        return """
<t t-name="%(xmlid)s">
    <t t-set="config"
       t-value="env['dynamic.report.config'].browse(%(config_id)d).exists()"/>
    <t t-call="dynamic_report_builder.report_dynamic_selected_base"/>
</t>
""" % {
            'xmlid': self._get_print_template_xmlid(),
            'config_id': self.id,
        }

    def _get_print_template_data(self):
        self.ensure_one()
        xml_name = 'report_dynamic_selected_config_%s' % self.id
        return self.env['ir.model.data'].sudo().search([
            ('module', '=', 'dynamic_report_builder'),
            ('name', '=', xml_name),
            ('model', '=', 'ir.ui.view'),
        ], limit=1)

    def _get_print_template_view(self):
        self.ensure_one()
        model_data = self._get_print_template_data()
        if not model_data:
            return self.env['ir.ui.view']
        return self.env['ir.ui.view'].sudo().browse(
            model_data.res_id
        ).exists()

    def _sync_print_template(self):
        IrModelData = self.env['ir.model.data'].sudo()
        View = self.env['ir.ui.view'].sudo()

        for rec in self:
            if not rec.id:
                continue

            xml_name = 'report_dynamic_selected_config_%s' % rec.id
            arch = rec._get_print_template_arch()
            model_data = rec._get_print_template_data()
            view = rec._get_print_template_view()

            if view:
                view.write({
                    'name': 'Dynamic Report Template - %s' % rec.name,
                    'type': 'qweb',
                    'arch_db': arch,
                })
                continue

            view = View.create({
                'name': 'Dynamic Report Template - %s' % rec.name,
                'type': 'qweb',
                'arch_db': arch,
            })
            if model_data:
                model_data.write({'res_id': view.id, 'noupdate': True})
            else:
                IrModelData.create({
                    'module': 'dynamic_report_builder',
                    'name': xml_name,
                    'model': 'ir.ui.view',
                    'res_id': view.id,
                    'noupdate': True,
                })

    def _has_report_columns(self):
        self.ensure_one()
        return bool(self.field_line_ids or self.field_ids)

    def _get_bound_print_server_code(self):
        self.ensure_one()
        return (
            "action = env['dynamic.report.config'].browse(%d)"
            ".action_print_selection(env.context.get('active_ids', []))"
            % self.id
        )

    def _get_bound_print_server_actions(self):
        self.ensure_one()
        if not self.id:
            return self.env['ir.actions.server']
        return self.env['ir.actions.server'].sudo().search([
            ('state', '=', 'code'),
            ('code', '=', self._get_bound_print_server_code()),
        ])

    def _sync_bound_print_server_action(self):
        for rec in self:
            if not rec.id or not rec.model_id or not rec._has_report_columns():
                if rec.id:
                    rec._get_bound_print_server_actions().unlink()
                continue

            actions = rec._get_bound_print_server_actions()
            vals = {
                'name': rec.name,
                # In Odoo 19 an ungrouped server action checks WRITE access
                # on the target model and selected records before running.
                # Printing is read-only, so mark the action for internal
                # users; actual report rows still obey read ACLs/rules.
                'group_ids': [(6, 0, [
                    self.env.ref('base.group_user').id,
                ])],
                'model_id': rec.model_id.id,
                'binding_model_id': rec.model_id.id,
                'binding_type': 'report',
                'state': 'code',
                'code': rec._get_bound_print_server_code(),
            }
            if actions:
                actions[:1].write(vals)
                (actions - actions[:1]).unlink()
            else:
                self.env['ir.actions.server'].sudo().create(vals)

    def _sync_print_action(self):
        for rec in self:
            rec._ensure_field_lines_from_legacy()
            if not rec.model_id or not rec._has_report_columns():
                print_action = rec.print_action_id
                template_view = (
                    rec._get_print_template_view()
                    if rec.id else self.env['ir.ui.view']
                )
                rec._sync_bound_print_server_action()
                if print_action:
                    rec.write({'print_action_id': False})
                    print_action.sudo().unlink()
                if template_view:
                    template_view.sudo().unlink()
                continue

            rec._sync_print_template()
            template_xmlid = rec._get_print_template_xmlid()
            vals = {
                'name': rec.name,
                'model': rec.model_id.sudo().model,
                'report_type': 'qweb-pdf',
                'report_name': template_xmlid,
                'report_file': template_xmlid,
                # Keep the real PDF action unbound. A bound server action is
                # shown in Print so it can open the date-range wizard first.
                'binding_model_id': False,
                'binding_type': 'report',
                'multi': True,
            }
            if not rec.print_action_id:
                action = self.env['ir.actions.report'].sudo().create(vals)
                rec.write({'print_action_id': action.id})
            else:
                rec.print_action_id.sudo().write(vals)
            rec._sync_bound_print_server_action()

    @api.model
    def _upgrade_sync_runtime_actions(self):
        configs = self.search([])
        configs._sync_menu_and_action()
        configs._sync_print_action()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_field_lines_from_legacy()
        records._sync_menu_and_action()
        records._sync_print_action()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'parent_menu_id' in vals:
            self._sync_menu_and_action()
        if {
            'name', 'model_id', 'field_ids', 'field_line_ids'
        }.intersection(vals):
            self._ensure_field_lines_from_legacy()
            self._sync_print_action()
        return res

    def unlink(self):
        menus = self.mapped('menu_id')
        actions = self.mapped('server_action_id')
        print_actions = self.mapped('print_action_id')
        template_views = self.env['ir.ui.view'].sudo()
        bound_print_actions = self.env['ir.actions.server'].sudo()
        for rec in self:
            template_views |= rec._get_print_template_view()
            bound_print_actions |= rec._get_bound_print_server_actions()
        res = super().unlink()
        menus.sudo().unlink()
        actions.sudo().unlink()
        print_actions.sudo().unlink()
        bound_print_actions.sudo().unlink()
        template_views.sudo().unlink()
        return res

    # ---------------------------------------------------------------
    # Report generation
    # ---------------------------------------------------------------
    def _has_runtime_filters(self):
        self.ensure_one()
        return bool(
            (self.enable_date_filter and self.date_field_id)
            or (self.enable_user_filter and self.user_field_id)
        )

    def _get_runtime_filter_title(self):
        self.ensure_one()
        has_date = bool(self.enable_date_filter and self.date_field_id)
        has_user = bool(self.enable_user_filter and self.user_field_id)
        if has_date and has_user:
            return _('Select Report Filters')
        if has_user:
            return _('Select User')
        return _('Select Date Range')

    def _open_runtime_filter_wizard(self, active_ids=None, source='selection'):
        self.ensure_one()
        if not self._has_runtime_filters():
            raise UserError(
                _('Please configure at least one runtime report filter first.')
            )
        active_ids = [int(record_id) for record_id in (active_ids or [])]
        return {
            'type': 'ir.actions.act_window',
            'name': self._get_runtime_filter_title(),
            'res_model': 'dynamic.report.date.filter.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'dynamic_report_builder.view_dynamic_report_date_filter_wizard_form'
            ).id,
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_source': source,
                'default_selected_ids': repr(active_ids),
                'default_selected_count': len(active_ids),
                # Pass visibility metadata explicitly so the first render of
                # a new transient wizard is never blank in the web client.
                'default_date_filter_enabled': bool(
                    self.enable_date_filter and self.date_field_id
                ),
                'default_date_field_label': (
                    self.date_field_id.sudo().field_description or False
                ),
                'default_user_filter_enabled': bool(
                    self.enable_user_filter and self.user_field_id
                ),
                'default_user_grouping_enabled': bool(self.group_by_user),
                'default_user_field_label': (
                    self.user_field_id.sudo().field_description or False
                ),
            },
        }

    def _open_date_filter_wizard(self, active_ids=None, source='selection'):
        """Backward-compatible alias for older generated actions."""
        return self._open_runtime_filter_wizard(active_ids, source)

    def action_print_selection(self, active_ids=None):
        self.ensure_one()
        active_ids = active_ids or []
        if not active_ids:
            raise UserError(_('Please select at least one record to print.'))
        if self._has_runtime_filters():
            return self._open_runtime_filter_wizard(
                active_ids=active_ids, source='selection'
            )
        if self.env.user.has_group('base.group_system'):
            self._sync_print_action()
        records = self.env[self.model_id.sudo().model].browse(active_ids).exists()
        if not records:
            raise UserError(_('No selected records are available to print.'))
        return self.print_action_id.report_action(
            records,
            data={
                'report_record_ids': records.ids,
                'report_date_from': False,
                'report_date_to': False,
                'report_user_id': False,
                'report_user_name': False,
            },
        )

    def action_open_generated_report(self):
        self.ensure_one()
        if self._has_runtime_filters():
            return self._open_runtime_filter_wizard(source='menu')
        return self.action_generate_report(skip_runtime_filters=True)

    def action_generate_report(self, skip_runtime_filters=False):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            self._ensure_field_lines_from_legacy()
        if not self.field_line_ids:
            raise UserError(
                _('Please add at least one report column before printing.')
            )

        if self._has_runtime_filters() and not skip_runtime_filters:
            return self._open_runtime_filter_wizard(source='menu')

        # Sync only during a normal user request, after the registry/schema is
        # fully loaded. This keeps upgrades safe when the ordered-column model
        # is introduced into an existing database.
        if self.env.user.has_group('base.group_system'):
            self._sync_menu_and_action()
            self._sync_print_action()

        # Open the PDF route directly in a new browser tab. Using an
        # ``ir.actions.act_url`` here avoids Odoo's ``report_download``
        # client flow, which forces a file download. The browser can render
        # the PDF inline so the user can review it before printing/saving.
        report_name = 'dynamic_report_builder.report_dynamic_document'
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/pdf/%s/%s' % (report_name, self.id),
            'target': 'new',
        }

    def _normalize_main_field_columns(self):
        """Normalize old UI selections that used a Many2one as a source.

        Main-model relational fields such as Vendor, Buyer or Customer are
        report columns themselves.  They must not be traversed through their
        comodel merely to read ``name``.  Only x2many fields are valid line
        sources for the column builder.
        """
        for config in self:
            for line in config.field_line_ids:
                source = line.relation_field_id.sudo()
                if not source or source.ttype in ('one2many', 'many2many'):
                    continue

                # Existing configurations created by the previous builder
                # commonly stored Vendor -> Name / Buyer -> Name.  Convert
                # those safely to the main field itself.
                leaf_name = line.field_id.sudo().name if line.field_id else False
                if source.ttype == 'many2one' and leaf_name in (
                    'name', 'display_name',
                ):
                    line.write({
                        'relation_field_id': False,
                        'field_id': source.id,
                    })
                else:
                    # A scalar/many2one source is never a line source.  Keep
                    # the chosen field only when it already belongs to the
                    # main model; otherwise clear the invalid source so the
                    # user can choose the intended main field.
                    vals = {'relation_field_id': False}
                    if (
                        line.field_id
                        and line.field_id.sudo().model != config.model_id.sudo().model
                    ):
                        vals['field_id'] = False
                    line.write(vals)

    def _get_ordered_columns(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            self._ensure_field_lines_from_legacy()
            self._normalize_main_field_columns()
        return self.field_line_ids.sorted(
            key=lambda line: (line.sequence, line.id)
        )

    def _get_date_filter_domain(self, date_from=False, date_to=False):
        """Build a date range domain using the configured date field."""
        self.ensure_one()
        if not self.enable_date_filter or not self.date_field_id:
            return []

        if self.date_field_id.sudo().model != self.model_id.sudo().model:
            return []
        if self.date_field_id.sudo().ttype not in ('date', 'datetime'):
            return []

        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                _('From Date cannot be later than To Date.')
            )

        field_name = self.date_field_id.sudo().name
        domain = []
        if self.date_field_id.sudo().ttype == 'date':
            if date_from:
                domain.append((
                    field_name, '>=', fields.Date.to_string(date_from)
                ))
            if date_to:
                domain.append((
                    field_name, '<=', fields.Date.to_string(date_to)
                ))
            return domain

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        if date_from:
            local_start = user_tz.localize(
                datetime.combine(date_from, time.min)
            )
            utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
            domain.append((
                field_name, '>=', fields.Datetime.to_string(utc_start)
            ))
        if date_to:
            next_day = date_to + timedelta(days=1)
            local_end = user_tz.localize(
                datetime.combine(next_day, time.min)
            )
            utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
            domain.append((
                field_name, '<', fields.Datetime.to_string(utc_end)
            ))
        return domain

    def _get_user_filter_domain(self, user_id=False):
        """Build a safe runtime user domain without bypassing record rules."""
        self.ensure_one()
        if not self.enable_user_filter or not self.user_field_id or not user_id:
            return []

        field_rec = self.user_field_id.sudo()
        if (
            field_rec.model != self.model_id.sudo().model
            or field_rec.ttype != 'many2one'
            or field_rec.relation != 'res.users'
            or not field_rec.store
            or field_rec.name in ('create_uid', 'write_uid')
        ):
            raise ValidationError(
                _('The configured User Field is no longer valid.')
            )
        return [(field_rec.name, '=', int(user_id))]

    def _get_user_grouped_records(self, records):
        """Return report records grouped by the configured user field."""
        self.ensure_one()
        if (
            not self.enable_user_filter
            or not self.group_by_user
            or not self.user_field_id
        ):
            return []

        field_name = self.user_field_id.sudo().name
        if field_name not in records._fields:
            return []

        grouped = {}
        unassigned = records.browse()
        for record in records:
            user = record[field_name]
            if user:
                grouped.setdefault(user.id, records.browse())
                grouped[user.id] |= record
            else:
                unassigned |= record

        result = []
        users = self.env['res.users'].browse(sorted(grouped)).exists()
        users = users.sorted(key=lambda user: (user.name or '').lower())
        for user in users:
            result.append({
                'key': user.id,
                'label': user.display_name,
                'records': grouped[user.id],
            })
        if unassigned:
            result.append({
                'key': False,
                'label': _('Unassigned'),
                'records': unassigned,
            })
        return result


    def _get_runtime_report_records(self, record_ids=None, fallback=None):
        """Resolve runtime report rows while preserving access rules/order.

        Dynamic report actions pass filter metadata through ``data``.  In that
        path Odoo can render the template without populating ``docs`` even
        though ``report_action`` received a recordset.  The wizard therefore
        passes the filtered IDs explicitly.  Resolve them again with ``search``
        so normal ACLs and record rules are still enforced, then restore the
        original report ordering.
        """
        self.ensure_one()
        Model = self.env[self.model_id.sudo().model]
        ids = []
        for record_id in record_ids or []:
            try:
                record_id = int(record_id)
            except (TypeError, ValueError):
                continue
            if record_id > 0 and record_id not in ids:
                ids.append(record_id)

        if not ids:
            return fallback or Model.browse()

        accessible = Model.search([('id', 'in', ids)])
        accessible_ids = set(accessible.ids)
        ordered_ids = [record_id for record_id in ids if record_id in accessible_ids]
        return Model.browse(ordered_ids)

    def _get_runtime_report_sections(self, records, columns=None):
        """Return safe report sections for normal and user-grouped output.

        Keeping section preparation in Python lets the QWeb template render the
        table directly.  This avoids relying on nested ``t-call`` variable
        scope for the selected-record report, which can otherwise result in an
        empty body even though the report title/layout is rendered.
        """
        self.ensure_one()
        if (
            self.enable_user_filter
            and self.group_by_user
            and self.user_field_id
        ):
            groups = self._get_user_grouped_records(records)
            if groups:
                sections = groups
            else:
                sections = [{
                    'key': False,
                    'label': False,
                    'records': records,
                }]
        else:
            sections = [{
                'key': False,
                'label': False,
                'records': records,
            }]

        for section in sections:
            section['rows'] = self._get_expanded_report_rows(
                section['records'], columns
            )
        return sections

    def _get_expanded_report_rows(self, records, columns=None):
        """Render x2many fields as individual rows rather than comma lists.

        Columns belonging to one line source stay together on each child row.
        Different line sources are printed in separate rows, never paired
        arbitrarily or combined into a Cartesian product. Main-model fields
        repeat on each row; parents without child lines retain one blank row.
        """
        self.ensure_one()
        if columns is None:
            columns = self._get_ordered_columns()

        column_specs = []
        source_names = []
        for column in columns:
            source_field = (
                column.relation_field_id.sudo()
                if column.relation_field_id else False
            )
            source_name = (
                source_field.name
                if source_field and source_field.ttype in ('one2many', 'many2many')
                else None
            )
            column_specs.append((column, source_name))
            if source_name and source_name not in source_names:
                source_names.append(source_name)

        rows = []
        for record in records:
            # Resolve main-model columns only once per parent, even when
            # multiple related records result in multiple printed rows.
            base_row = [
                self._format_column(record, column) if not source_name else ''
                for column, source_name in column_specs
            ]
            expanded = False
            for source_name in source_names:
                relation_field = record._fields.get(source_name)
                if not relation_field or relation_field.type not in (
                    'one2many', 'many2many',
                ):
                    continue
                try:
                    line_records = record[source_name]
                except Exception:
                    # Follow _format_column's existing behavior for fields
                    # the current user cannot read.
                    continue

                for line_record in line_records:
                    expanded = True
                    row = list(base_row)
                    for index, (column, column_source) in enumerate(column_specs):
                        if column_source == source_name and column.field_id:
                            row[index] = self._format_value(
                                line_record, column.field_id.sudo().name,
                                column=column,
                            )
                    rows.append(row)

            if not expanded:
                rows.append(base_row)
        return rows

    def get_report_data(self):
        self.ensure_one()
        model_name = self.model_id.sudo().model
        if model_name not in self.env:
            raise UserError(_('Model %s not found.') % model_name)

        try:
            domain = safe_eval(self.domain_filter or '[]')
            if not isinstance(domain, list):
                domain = []
        except Exception:
            domain = []


        order = False
        if (
            self.sort_field_id
            and self.sort_field_id.sudo().model == model_name
            and self.sort_field_id.sudo().store
        ):
            order = '%s %s' % (
                self.sort_field_id.sudo().name,
                self.sort_direction or 'asc',
            )

        records = self.env[model_name].search(
            domain,
            limit=self.limit or 1000,
            order=order,
        )
        columns = self._get_ordered_columns()
        rows = self._get_expanded_report_rows(records, columns)

        return {
            'headers': [column.get_display_label() for column in columns],
            'rows': rows,
            'model_description': self.model_id.sudo().name,
            'total': len(rows),
        }

    def _format_column(self, record, column):
        """Format a direct field or a one-hop relational/line field."""
        if not column.field_id:
            return ''

        if not column.relation_field_id:
            return self._format_value(
                record, column.field_id.sudo().name, column=column
            )

        relation_name = column.relation_field_id.sudo().name
        relation_field = record._fields.get(relation_name)
        if not relation_field:
            return ''

        try:
            related_records = record[relation_name]
        except Exception:
            return ''

        if not related_records:
            return ''

        values = []
        for related_record in related_records:
            value = self._format_value(
                related_record,
                column.field_id.sudo().name, column=column,
            )
            if value not in ('', False, None):
                values.append(str(value))
        return ', '.join(values)

    @staticmethod
    def _is_duration_column(field, field_name, column=None):
        """Match float_time-style attendance columns without changing other floats.

        The displayed report label can differ from the actual Odoo field name
        (for example ``overtime_hours`` is shown as Worked Extra Hours).
        """
        if field.type != 'float':
            return False
        names = {field_name.casefold().replace('_', ' ')}
        if field.string:
            names.add(field.string.casefold().replace('_', ' '))
        if column:
            names.add((column.get_display_label() or '').casefold().replace('_', ' '))
        recognized = {
            'worked hours', 'worked extra hours', 'extra worked hours',
            'overtime hours', 'overtime', 'extra hours', 'worked extra hour',
        }
        return bool(names & recognized)

    @staticmethod
    def _format_duration_hours(value):
        """Format decimal hours using the HH:MM Odoo float_time convention."""
        total_minutes = int(round(abs(value) * 60))
        hours, minutes = divmod(total_minutes, 60)
        return '%s%02d:%02d' % (
            '-' if value < 0 and total_minutes else '', hours, minutes,
        )

    def _format_value(self, record, field_name, column=None):
        field = record._fields.get(field_name)
        if not field:
            return ''
        try:
            value = record[field_name]
        except Exception:
            return ''

        if field.type == 'many2one':
            if not value:
                return ''
            display_name = value.display_name
            return str(display_name) if display_name not in (False, None) else ''
        if field.type in ('one2many', 'many2many'):
            if not value:
                return ''
            names = []
            for related_record in value:
                display_name = related_record.display_name
                if display_name not in (False, None, ''):
                    names.append(str(display_name))
            return ', '.join(names)
        if field.type == 'selection':
            selection = field.selection
            if callable(selection):
                selection = field._description_selection(record.env)
            selection_dict = dict(selection) if selection else {}
            return selection_dict.get(value, value or '')
        if field.type == 'boolean':
            return _('Yes') if value else _('No')
        if field.type == 'monetary':
            return value if value is not None else 0.0
        # Keep attendance float_time fields in the same visible HH:MM form as
        # the Odoo list/form widget, even when the technical field is called
        # overtime_hours rather than worked_extra_hours.
        if self._is_duration_column(field, field_name, column):
            if value is False or value is None:
                return ''
            return self._format_duration_hours(value)
        if value is False or value is None:
            return ''
        return value


class DynamicReportConfigField(models.Model):
    _name = 'dynamic.report.config.field'
    _description = 'Dynamic Report Column'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'dynamic.report.config',
        string='Report',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    main_model_name = fields.Char(
        string='Main Model Name',
        compute='_compute_model_names',
    )
    target_model_name = fields.Char(
        string='Target Model Name',
        compute='_compute_model_names',
    )
    relation_field_id = fields.Many2one(
        'ir.model.fields',
        string='Source / Line',
        ondelete='cascade',
        help=(
            'Leave empty for a field on the main model. Select a relational '
            'field such as Order Lines to choose a field from that line model.'
        ),
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        help='The field that will become a report column.',
    )
    custom_label = fields.Char(
        string='Column Label',
        help='Optional custom heading. Leave empty to use the field label.',
    )
    width = fields.Integer(
        string='Width %',
        default=0,
        help='Optional column width percentage. Use 0 for automatic width.',
    )
    alignment = fields.Selection(
        [
            ('auto', 'Auto'),
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right'),
        ],
        string='Alignment',
        default='auto',
        required=True,
    )

    @api.constrains('width')
    def _check_width(self):
        for line in self:
            if line.width < 0 or line.width > 100:
                raise UserError(_('Column width must be between 0 and 100.'))

    @api.depends(
        'config_id.model_id.model',
        'relation_field_id.relation',
    )
    def _compute_model_names(self):
        for line in self:
            main_model = line.config_id.model_id.sudo().model or False
            line.main_model_name = main_model
            line.target_model_name = (
                line.relation_field_id.sudo().relation
                if line.relation_field_id
                and line.relation_field_id.sudo().relation
                else main_model
            )

    @api.onchange('relation_field_id')
    def _onchange_relation_field_id(self):
        for line in self:
            if (
                line.relation_field_id
                and line.relation_field_id.sudo().ttype
                not in ('one2many', 'many2many')
            ):
                line.relation_field_id = False
            line.field_id = False

    def get_display_label(self):
        self.ensure_one()
        return self.custom_label or self.field_id.sudo().field_description or ''

    def get_effective_alignment(self):
        self.ensure_one()
        if self.alignment and self.alignment != 'auto':
            return self.alignment
        if self.field_id.sudo().ttype in (
            'integer', 'float', 'monetary', 'boolean',
        ):
            return 'right'
        if self.field_id.sudo().ttype in ('date', 'datetime', 'selection'):
            return 'center'
        return 'left'

    def get_header_style(self):
        self.ensure_one()
        styles = ['text-align:center', 'vertical-align:middle']
        if self.width:
            styles.append('width:%s%%' % self.width)
        return ';'.join(styles)

    def get_cell_style(self):
        self.ensure_one()
        styles = [
            'text-align:%s' % self.get_effective_alignment(),
            'vertical-align:middle',
        ]
        if self.width:
            styles.append('width:%s%%' % self.width)
        return ';'.join(styles)
