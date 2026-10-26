# -*- coding: utf-8 -*-

import calendar
from datetime import date, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class DynamicReportDateFilterWizard(models.TransientModel):
    _name = 'dynamic.report.date.filter.wizard'
    _description = 'Dynamic Report Date Filter'

    config_id = fields.Many2one(
        'dynamic.report.config',
        string='Report',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    source = fields.Selection(
        [('selection', 'Selected Records'), ('menu', 'Report Menu')],
        string='Source',
        required=True,
        default='selection',
        readonly=True,
    )
    selected_ids = fields.Text(string='Selected Record IDs', readonly=True)
    selected_count = fields.Integer(string='Selected Records', readonly=True)
    # Keep runtime filter metadata as normal transient fields instead of
    # related fields.  A wizard opened with default_config_id is initially an
    # unsaved virtual record in the web client; related fields may therefore
    # render as False on the very first popup.  Explicit defaults make the
    # Date/User sections visible immediately, including when the wizard is
    # opened from a list-view multi-selection Print action.
    date_field_label = fields.Char(string='Date Field', readonly=True)
    date_filter_enabled = fields.Boolean(
        string='Date Filter Enabled',
        readonly=True,
    )
    user_filter_enabled = fields.Boolean(
        string='User Filter Enabled',
        readonly=True,
    )
    user_grouping_enabled = fields.Boolean(
        string='Group By User',
        readonly=True,
    )
    user_field_label = fields.Char(string='User Field', readonly=True)
    user_id = fields.Many2one(
        'res.users',
        string='User',
        help=(
            'Leave blank to include all users you are allowed to see, or '
            'select a user to filter the report to that user.'
        ),
    )
    range_type = fields.Selection(
        [
            ('yearly', 'Yearly'),
            ('quarterly', 'Quarterly'),
            ('monthly', 'Monthly'),
            ('weekly', 'Weekly'),
            ('custom', 'Custom Dates'),
        ],
        string='Period',
        required=True,
        default='monthly',
    )
    period_year = fields.Integer(
        string='Year',
        default=lambda self: fields.Date.context_today(self).year,
    )
    period_quarter = fields.Selection(
        [
            ('1', 'Q1 (Jan - Mar)'),
            ('2', 'Q2 (Apr - Jun)'),
            ('3', 'Q3 (Jul - Sep)'),
            ('4', 'Q4 (Oct - Dec)'),
        ],
        string='Quarter',
        default=lambda self: str(
            ((fields.Date.context_today(self).month - 1) // 3) + 1
        ),
    )
    period_month = fields.Selection(
        [(str(month), calendar.month_name[month]) for month in range(1, 13)],
        string='Month',
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    period_week = fields.Integer(
        string='ISO Week',
        default=lambda self: fields.Date.context_today(self).isocalendar().week,
    )
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')

    selected_period_label = fields.Char(
        string='Selected Period',
        compute='_compute_period_labels',
    )
    month_label = fields.Char(
        string='Month Label',
        compute='_compute_period_labels',
    )
    quarter_label = fields.Char(
        string='Quarter Label',
        compute='_compute_period_labels',
    )
    week_label = fields.Char(
        string='Week Label',
        compute='_compute_period_labels',
    )
    year_label = fields.Char(
        string='Year Label',
        compute='_compute_period_labels',
    )
    effective_range_label = fields.Char(
        string='Effective Range',
        compute='_compute_period_labels',
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        config_id = values.get('config_id') or self.env.context.get(
            'default_config_id'
        )
        config = self.env['dynamic.report.config'].browse(config_id).exists()
        if config:
            values.setdefault(
                'date_filter_enabled',
                bool(config.enable_date_filter and config.date_field_id),
            )
            values.setdefault(
                'date_field_label',
                config._get_date_field_display_label(),
            )
            values.setdefault(
                'user_filter_enabled',
                bool(config.enable_user_filter and config.user_field_id),
            )
            values.setdefault(
                'user_grouping_enabled',
                bool(config.group_by_user),
            )
            values.setdefault(
                'user_field_label',
                config.user_field_id.sudo().field_description or False,
            )

        today = fields.Date.context_today(self)
        values.setdefault('range_type', 'monthly')
        values.setdefault('period_year', today.year)
        values.setdefault('period_month', str(today.month))
        values.setdefault('period_quarter', str(((today.month - 1) // 3) + 1))
        values.setdefault('period_week', today.isocalendar().week)

        if values.get('range_type') == 'monthly':
            month = int(values.get('period_month') or today.month)
            year = int(values.get('period_year') or today.year)
            values.setdefault('date_from', date(year, month, 1))
            values.setdefault(
                'date_to',
                date(year, month, calendar.monthrange(year, month)[1]),
            )
        return values

    @api.depends(
        'range_type',
        'period_year',
        'period_quarter',
        'period_month',
        'period_week',
        'date_from',
        'date_to',
    )
    def _compute_period_labels(self):
        for wizard in self:
            year = wizard.period_year or fields.Date.context_today(wizard).year
            month = int(
                wizard.period_month
                or fields.Date.context_today(wizard).month
            )
            quarter = int(
                wizard.period_quarter
                or (((fields.Date.context_today(wizard).month - 1) // 3) + 1)
            )
            week = wizard.period_week or fields.Date.context_today(
                wizard
            ).isocalendar().week

            wizard.month_label = '%s %s' % (calendar.month_name[month], year)

            quarter_start = ((quarter - 1) * 3) + 1
            quarter_end = quarter_start + 2
            wizard.quarter_label = '%s - %s %s' % (
                calendar.month_abbr[quarter_start],
                calendar.month_abbr[quarter_end],
                year,
            )

            wizard.year_label = str(year)
            wizard.week_label = _('Week %(week)s, %(year)s') % {
                'week': week,
                'year': year,
            }

            if wizard.range_type == 'monthly':
                wizard.selected_period_label = wizard.month_label
            elif wizard.range_type == 'quarterly':
                wizard.selected_period_label = wizard.quarter_label
            elif wizard.range_type == 'weekly':
                wizard.selected_period_label = wizard.week_label
            elif wizard.range_type == 'yearly':
                wizard.selected_period_label = wizard.year_label
            else:
                wizard.selected_period_label = _('Custom Dates')

            try:
                date_from, date_to = wizard._get_period_dates(strict=False)
            except (TypeError, ValueError):
                date_from, date_to = False, False

            if date_from and date_to:
                wizard.effective_range_label = _(
                    '%(date_from)s to %(date_to)s'
                ) % {
                    'date_from': fields.Date.to_string(date_from),
                    'date_to': fields.Date.to_string(date_to),
                }
            elif date_from:
                wizard.effective_range_label = _('From %(date_from)s') % {
                    'date_from': fields.Date.to_string(date_from),
                }
            elif date_to:
                wizard.effective_range_label = _('Up to %(date_to)s') % {
                    'date_to': fields.Date.to_string(date_to),
                }
            else:
                wizard.effective_range_label = _('All available dates')

    @api.onchange(
        'range_type',
        'period_year',
        'period_quarter',
        'period_month',
        'period_week',
    )
    def _onchange_period(self):
        for wizard in self:
            if wizard.range_type == 'custom':
                continue
            date_from, date_to = wizard._get_period_dates(strict=False)
            wizard.date_from = date_from
            wizard.date_to = date_to

    def _get_period_dates(self, strict=True):
        self.ensure_one()
        if self.range_type == 'custom':
            # Selecting Custom Dates without either boundary previously
            # generated an unfiltered PDF without telling the user.
            if strict and not (self.date_from or self.date_to):
                raise ValidationError(
                    _('Please select at least one Custom Date boundary.')
                )
            return self.date_from, self.date_to

        year = self.period_year
        if not 1 <= year <= 9999:
            if strict:
                raise ValidationError(_('Please enter a valid year.'))
            return False, False

        if self.range_type == 'yearly':
            return date(year, 1, 1), date(year, 12, 31)

        if self.range_type == 'quarterly':
            if not self.period_quarter:
                if strict:
                    raise ValidationError(_('Please select a quarter.'))
                return False, False
            quarter = int(self.period_quarter)
            start_month = ((quarter - 1) * 3) + 1
            end_month = start_month + 2
            return (
                date(year, start_month, 1),
                date(
                    year,
                    end_month,
                    calendar.monthrange(year, end_month)[1],
                ),
            )

        if self.range_type == 'monthly':
            if not self.period_month:
                if strict:
                    raise ValidationError(_('Please select a month.'))
                return False, False
            month = int(self.period_month)
            return (
                date(year, month, 1),
                date(year, month, calendar.monthrange(year, month)[1]),
            )

        if self.range_type == 'weekly':
            if not 1 <= self.period_week <= 53:
                if strict:
                    raise ValidationError(
                        _('ISO Week must be between 1 and 53.')
                    )
                return False, False
            try:
                return (
                    date.fromisocalendar(year, self.period_week, 1),
                    date.fromisocalendar(year, self.period_week, 7),
                )
            except ValueError:
                if strict:
                    raise ValidationError(
                        _('Week %(week)s does not exist in %(year)s.') % {
                            'week': self.period_week,
                            'year': year,
                        }
                    )
                return False, False

        return False, False

    def _sync_effective_dates(self):
        self.ensure_one()
        if self.range_type == 'custom':
            return
        date_from, date_to = self._get_period_dates(strict=False)
        self.write({
            'date_from': date_from,
            'date_to': date_to,
        })

    def _reopen_wizard(self):
        """Keep the same modal open after period selection/navigation."""
        self.ensure_one()
        view = self.env.ref(
            'dynamic_report_builder.view_dynamic_report_date_filter_wizard_form'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': self.config_id._get_runtime_filter_title(),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }

    def action_select_period(self):
        self.ensure_one()
        period_key = self.env.context.get('period_key')
        allowed_periods = {'monthly', 'quarterly', 'weekly', 'yearly', 'custom'}
        if period_key not in allowed_periods:
            raise UserError(_('Unsupported reporting period.'))
        self.range_type = period_key
        self._sync_effective_dates()
        return self._reopen_wizard()

    def action_navigate_period(self):
        self.ensure_one()
        period_key = self.env.context.get('period_key')
        direction = int(self.env.context.get('direction', 0))
        if period_key not in {'monthly', 'quarterly', 'weekly', 'yearly'}:
            raise UserError(_('Unsupported reporting period.'))
        if direction not in {-1, 1}:
            raise UserError(_('Invalid navigation direction.'))

        self.range_type = period_key
        year = self.period_year

        if period_key == 'monthly':
            month = int(self.period_month)
            month_index = (year * 12) + month - 1 + direction
            new_year, month_zero_based = divmod(month_index, 12)
            self.period_year = new_year
            self.period_month = str(month_zero_based + 1)

        elif period_key == 'quarterly':
            quarter = int(self.period_quarter)
            quarter_index = (year * 4) + quarter - 1 + direction
            new_year, quarter_zero_based = divmod(quarter_index, 4)
            self.period_year = new_year
            self.period_quarter = str(quarter_zero_based + 1)

        elif period_key == 'weekly':
            try:
                week_start = date.fromisocalendar(year, self.period_week, 1)
            except ValueError:
                week_start = date(year, 1, 4)
                week_start -= timedelta(days=week_start.isoweekday() - 1)
            target = week_start + timedelta(days=7 * direction)
            iso_year, iso_week, _ = target.isocalendar()
            self.period_year = iso_year
            self.period_week = iso_week

        else:
            self.period_year = year + direction

        self._sync_effective_dates()
        return self._reopen_wizard()

    def _get_selected_ids(self):
        self.ensure_one()
        try:
            ids = safe_eval(self.selected_ids or '[]')
        except Exception:
            ids = []
        if not isinstance(ids, list):
            return []
        return [record_id for record_id in ids if isinstance(record_id, int)]

    def action_print_report(self):
        self.ensure_one()
        config = self.config_id.exists()
        if not config:
            raise UserError(_('The report configuration no longer exists.'))
        if not config._has_runtime_filters():
            raise UserError(
                _('No runtime filter is configured for this report.')
            )

        date_from = False
        date_to = False
        date_domain = []
        if config.enable_date_filter and config.date_field_id:
            date_from, date_to = self._get_period_dates(strict=True)
            if date_from and date_to and date_from > date_to:
                raise ValidationError(
                    _('From Date cannot be later than To Date.')
                )
            date_domain = config._get_date_filter_domain(date_from, date_to)

        user_domain = []
        selected_user = self.user_id.exists()
        if config.enable_user_filter and config.user_field_id and selected_user:
            user_domain = config._get_user_filter_domain(selected_user.id)

        model_name = config.model_id.sudo().model
        Model = self.env[model_name]

        order = False
        if (
            config.sort_field_id
            and config.sort_field_id.sudo().model == model_name
            and config.sort_field_id.sudo().store
        ):
            order = '%s %s' % (
                config.sort_field_id.sudo().name,
                config.sort_direction or 'asc',
            )

        runtime_domain = date_domain + user_domain
        if self.source == 'selection':
            selected_ids = self._get_selected_ids()
            if not selected_ids:
                raise UserError(_('Please select at least one record to print.'))
            domain = [('id', 'in', selected_ids)] + runtime_domain
            records = Model.search(domain, order=order)
        else:
            try:
                domain = safe_eval(config.domain_filter or '[]')
                if not isinstance(domain, list):
                    domain = []
            except Exception:
                domain = []
            domain += runtime_domain
            records = Model.search(
                domain,
                limit=config.limit or 1000,
                order=order,
            )

        if not records:
            raise UserError(
                _('No records were found for the selected report filters.')
            )

        # Resolve/migrate report columns before entering QWeb.  Existing
        # configurations may still use the legacy Many2many field list; doing
        # this here guarantees the first generated PDF has its information
        # table instead of rendering only the title/layout.
        columns = config._get_ordered_columns()
        if not columns:
            raise UserError(
                _('Please add at least one report column before printing.')
            )

        # Report bindings are created by administrators when configuring reports.
        # Printing must not write actions or require configuration privileges.
        if self.env.user.has_group('base.group_system'):
            config._sync_print_action()
        period_label_map = {
            'monthly': _('Month'),
            'quarterly': _('Quarter'),
            'weekly': _('Week'),
            'yearly': _('Year'),
            'custom': _('Custom Dates'),
        }
        period_label = period_label_map.get(self.range_type)
        period_value = False
        if config.enable_date_filter and config.date_field_id:
            if self.range_type == 'custom':
                period_value = self.effective_range_label or False
            else:
                period_value = self.selected_period_label or False

        report_data = {
            # When a report action carries custom ``data``, the standard QWeb
            # rendering path may not reliably expose ``docs`` for dynamically
            # generated report actions.  Carry the already-filtered record IDs
            # explicitly so the template can resolve the exact report rows.
            'report_record_ids': records.ids,
            'report_date_from': (
                fields.Date.to_string(date_from) if date_from else False
            ),
            'report_date_to': (
                fields.Date.to_string(date_to) if date_to else False
            ),
            'report_period_label': period_label,
            'report_period_value': period_value,
            'report_user_id': selected_user.id if selected_user else False,
            'report_user_name': (
                selected_user.display_name if selected_user else False
            ),
        }
        report_context = {
            # Keep explicit boundaries in context as well as report data.
            # The PDF-side row expansion must use the same date range as the
            # wizard search, including when the report client re-renders it.
            'dynamic_report_date_from': report_data['report_date_from'],
            'dynamic_report_date_to': report_data['report_date_to'],
            'dynamic_report_period_label': period_label,
            'dynamic_report_period_value': period_value,
            'dynamic_report_filter_label': (
                config.user_field_id.sudo().field_description
                if selected_user and config.user_field_id
                else False
            ),
            'dynamic_report_filter_value': (
                selected_user.display_name if selected_user else False
            ),
        }
        return config.print_action_id.with_context(
            **report_context
        ).report_action(
            records,
            data=report_data,
        )
