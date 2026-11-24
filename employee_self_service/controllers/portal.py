# -*- coding: utf-8 -*-
from collections import OrderedDict
import base64
import logging

from odoo import _, fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request

_logger = logging.getLogger(__name__)


class EmployeePortal(CustomerPortal):
    PAYSLIP_VISIBLE_STATES = ['validated', 'paid']

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        employee = self._get_current_employee()

        if 'payslip_count' in counters:
            values['payslip_count'] = request.env['hr.payslip'].sudo().search_count([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['validated', 'paid']),
            ]) if employee else 0

        if 'attendance_count' in counters:
            values['attendance_count'] = request.env['hr.attendance'].sudo().search_count([
                ('employee_id', '=', employee.id),
            ]) if employee else 0

        if 'timeoff_count' in counters:
            values['timeoff_count'] = request.env['hr.leave'].sudo().search_count([
                ('employee_id', '=', employee.id),
            ]) if employee else 0

        return values

    def _get_current_employee(self):
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        if not employee and request.env.user.email:
            employee = request.env['hr.employee'].sudo().search([
                ('work_email', '=', request.env.user.email),
            ], limit=1)
        return employee

    def _redirect_if_no_employee(self):
        employee = self._get_current_employee()
        if not employee:
            return None, None
        return employee, None

    def _field_value(self, employee, field_name):
        field = employee._fields.get(field_name)
        if not field:
            return False
        value = employee[field_name]
        if value in (False, None, '', []):
            return False
        if getattr(field, 'type', None) == 'many2one':
            return value.display_name or value.name
        if getattr(field, 'type', None) == 'many2many':
            return ', '.join(value.mapped('display_name'))
        if getattr(field, 'type', None) == 'boolean':
            return _('Yes') if value else _('No')
        return str(value)

    def _make_items(self, employee, fields_map):
        items = []
        for field_name, label in fields_map:
            value = self._field_value(employee, field_name)
            if value:
                items.append({'label': label, 'value': value})
        return items

    def _first_field_value(self, employee, field_names):
        for field_name in field_names:
            value = self._field_value(employee, field_name)
            if value:
                return value
        return False

    def _make_items_flexible(self, employee, fields_map):
        items = []
        for field_names, label in fields_map:
            names = field_names if isinstance(field_names, (list, tuple)) else [field_names]
            value = self._first_field_value(employee, names)
            if value:
                items.append({'label': label, 'value': value})
        return items

    def _get_portal_allowed_leave_types(self, employee, search_term=''):
        """
        Return leave types allowed for this employee:
        1) validated allocated leave types for this employee
        2) leave types that do not require allocation AND match employee country
        """
        LeaveType = request.env['hr.leave.type'].sudo().with_context(
            employee_id=employee.id,
            default_employee_id=employee.id,
            allowed_company_ids=[employee.company_id.id],
        )

        Allocation = request.env['hr.leave.allocation'].sudo().with_context(
            employee_id=employee.id,
            default_employee_id=employee.id,
            allowed_company_ids=[employee.company_id.id],
        )

        search_value = (search_term or '').strip()
        employee_country = employee.company_id.country_id

        # ---------------------------------------------------
        # 1) Allocated leave types for this employee only
        # ---------------------------------------------------
        allocation_domain = [
            ('state', '=', 'validate'),
            ('holiday_status_id', '!=', False),
            ('employee_id', '=', employee.id),
        ]

        allocations = Allocation.search(allocation_domain)
        allocated_leave_types = allocations.mapped('holiday_status_id').filtered(lambda lt: lt.active)

        # ---------------------------------------------------
        # 2) Portal should show only leave types that require allocation
        #    and are actually allocated to this employee.
        # ---------------------------------------------------
        leave_types = allocated_leave_types.filtered(lambda lt: lt.active)

        if 'requires_allocation' in LeaveType._fields:
            field = LeaveType._fields['requires_allocation']
            if field.type == 'boolean':
                leave_types = leave_types.filtered(lambda lt: lt.requires_allocation)
            else:
                leave_types = leave_types.filtered(lambda lt: lt.requires_allocation != 'no')
        elif 'allocation_type' in LeaveType._fields:
            leave_types = leave_types.filtered(lambda lt: lt.allocation_type != 'no')
        else:
            leave_types = leave_types.browse([])

        # country filter
        if 'country_id' in LeaveType._fields:
            if employee_country:
                leave_types = leave_types.filtered(lambda lt: not lt.country_id or lt.country_id.id == employee_country.id)
            else:
                leave_types = leave_types.filtered(lambda lt: not lt.country_id)

        # Hide types from portal when custom checkbox is enabled
        if 'hide_on_dashboard' in LeaveType._fields:
            leave_types = leave_types.filtered(lambda lt: not lt.hide_on_dashboard)

        if search_value:
            search_lower = search_value.lower()
            leave_types = leave_types.filtered(
                lambda lt: search_lower in (lt.name or '').lower()
            )

        leave_types = leave_types.sorted(key=lambda lt: (lt.sequence, lt.id))
        return leave_types

    @http.route(['/my/payslips', '/my/payslips/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_payslips(self, page=1, sortby=None, filterby=None, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'date_to desc'},
            'name': {'label': _('Reference'), 'order': 'name asc'},
            'state': {'label': _('Status'), 'order': 'state asc'},
        }
        sortby = sortby or 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = OrderedDict([
            ('all', {'label': _('All'), 'domain': []}),
            ('validated', {'label': _('Validated'), 'domain': [('state', '=', 'validated')]}),
            ('paid', {'label': _('Paid'), 'domain': [('state', '=', 'paid')]}),
        ])
        filterby = filterby or 'all'
        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_VISIBLE_STATES),
        ] + searchbar_filters[filterby]['domain']

        payslip_count = request.env['hr.payslip'].sudo().search_count(domain)
        pager = portal_pager(url='/my/payslips', url_args={'sortby': sortby, 'filterby': filterby}, total=payslip_count, page=page, step=10)
        payslips = request.env['hr.payslip'].sudo().search(domain, order=order, limit=10, offset=pager['offset'])

        values = {
            'employee': employee,
            'payslips': payslips,
            'page_name': 'payslip',
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'default_url': '/my/payslips',
        }
        return request.render('employee_self_service.portal_my_payslips', values)

    @http.route(['/my/payslips/<int:payslip_id>'], type='http', auth='user', website=True)
    def portal_payslip_detail(self, payslip_id, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        payslip = request.env['hr.payslip'].sudo().search([
            ('id', '=', payslip_id),
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_VISIBLE_STATES),
        ], limit=1)
        if not payslip:
            return request.not_found()

        values = {
            'payslip': payslip,
            'employee': employee,
            'page_name': 'payslip',
            'lines': payslip.line_ids.filtered(lambda l: l.appears_on_payslip),
        }
        return request.render('employee_self_service.portal_payslip_detail', values)

    @http.route(['/my/payslips/<int:payslip_id>/preview'], type='http', auth='user', website=True)
    def portal_payslip_preview(self, payslip_id, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        payslip = request.env['hr.payslip'].sudo().search([
            ('id', '=', payslip_id),
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_VISIBLE_STATES),
        ], limit=1)
        if not payslip:
            return request.not_found()

        pdf_content, content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf('hr_payroll.action_report_payslip', payslip.ids)
        filename = f"Payslip_{(payslip.name or 'payslip').replace('/', '_')}.pdf"
        return request.make_response(pdf_content, headers=[('Content-Type', 'application/pdf'), ('Content-Disposition', f'inline; filename="{filename}"')])

    @http.route(['/my/payslips/<int:payslip_id>/download'], type='http', auth='user', website=True)
    def portal_payslip_download(self, payslip_id, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        payslip = request.env['hr.payslip'].sudo().search([
            ('id', '=', payslip_id),
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_VISIBLE_STATES),
        ], limit=1)
        if not payslip:
            return request.not_found()

        pdf_content, content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf('hr_payroll.action_report_payslip', payslip.ids)
        filename = f"Payslip_{(payslip.name or 'payslip').replace('/', '_')}.pdf"
        return request.make_response(pdf_content, headers=[('Content-Type', 'application/pdf'), ('Content-Disposition', f'attachment; filename="{filename}"')])

    @http.route(['/my/employee-portal'], type='http', auth='user', website=True)
    def employee_portal_home(self, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        payslip_count = request.env['hr.payslip'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('state', 'in', self.PAYSLIP_VISIBLE_STATES),
        ]) if employee else 0
        attendance_count = request.env['hr.attendance'].sudo().search_count([
            ('employee_id', '=', employee.id),
        ]) if employee else 0
        timeoff_count = request.env['hr.leave'].sudo().search_count([
            ('employee_id', '=', employee.id),
        ]) if employee else 0
        return request.render('employee_self_service.employee_portal_home', {
            'employee': employee,
            'payslip_count': payslip_count,
            'attendance_count': attendance_count,
            'timeoff_count': timeoff_count,
        })

    @http.route(['/my/attendances', '/my/attendances/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_attendances(self, page=1, sortby=None, filterby=None, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'check_in desc'},
            'worked_hours': {'label': _('Worked Hours'), 'order': 'worked_hours desc'},
        }
        sortby = sortby or 'date'
        order = searchbar_sortings[sortby]['order']

        today = fields.Date.today()
        first_day_this_month = today.replace(day=1)
        searchbar_filters = OrderedDict([
            ('this_month', {'label': _('This Month'), 'domain': [('check_in', '>=', first_day_this_month.strftime('%Y-%m-%d 00:00:00'))]}),
            ('all', {'label': _('All'), 'domain': []}),
        ])
        filterby = filterby or 'this_month'
        domain = [('employee_id', '=', employee.id)] + searchbar_filters[filterby]['domain']

        attendance_count = request.env['hr.attendance'].sudo().search_count(domain)
        pager = portal_pager(url='/my/attendances', url_args={'sortby': sortby, 'filterby': filterby}, total=attendance_count, page=page, step=20)
        attendances = request.env['hr.attendance'].sudo().search(domain, order=order, limit=20, offset=pager['offset'])
        total_hours = sum(attendances.mapped('worked_hours'))
        total_days = len(attendances)

        values = {
            'employee': employee,
            'attendances': attendances,
            'total_hours': total_hours,
            'total_days': total_days,
            'page_name': 'attendance',
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'default_url': '/my/attendances',
        }
        return request.render('employee_self_service.portal_my_attendances', values)

    @http.route(['/my/personal-details'], type='http', auth='user', website=True)
    def portal_my_personal_details(self, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        private_contact_items = self._make_items(employee, [
            ('private_email', _('Email')),
            ('phone', _('Phone')),
            ('bank_account_id', _('Bank Account')),
        ])

        personal_info_items = self._make_items(employee, [
            ('name', _('Legal Name')),
            ('birthday', _('Birthday')),
            ('place_of_birth', _('Place of Birth')),
            ('country_of_birth', _('Country of Birth')),
            ('gender', _('Gender')),
            ('is_muslim', _('Is Muslim')),
            ('lang', _('Payslip Language')),
        ])

        emergency_items = self._make_items(employee, [
            ('emergency_contact', _('Contact')),
            ('emergency_phone', _('Phone')),
        ])

        citizenship_items = self._make_items_flexible(employee, [
            ('country_id', _('Nationality')),
            ('non_resident', _('Non-resident')),
            ('identification_id', _('Identification No')),
            ('ssnid', _('SSN No')),
            ('passport_id', _('Passport No')),
            (('passport_expiration_date', 'passport_expire', 'passport_date_of_expiry'), _('Passport Expires On')),
        ])

        visa_items = self._make_items_flexible(employee, [
            ('visa_no', _('Visa No')),
            (('visa_expire', 'visa_expiration_date', 'visa_date_of_expiry'), _('Visa Expires On')),
            ('permit_no', _('Work Permit No')),
            (('work_permit_expiration_date', 'permit_expire', 'work_permit_expire'), _('Work Permit Expires On')),
        ])

        address_lines = [
            self._field_value(employee, 'private_street'),
            self._field_value(employee, 'private_street2'),
            self._field_value(employee, 'private_city'),
            self._field_value(employee, 'private_state_id'),
            self._field_value(employee, 'private_zip'),
            self._field_value(employee, 'private_country_id'),
        ]
        location_items = []
        address_value = ', '.join([line for line in address_lines if line])
        if address_value:
            location_items.append({'label': _('Private Address'), 'value': address_value})
        location_items += self._make_items(employee, [
            ('km_home_work', _('Home-Work Distance')),
        ])

        values = {
            'employee': employee,
            'page_name': 'personal_details',
            'private_contact_items': private_contact_items,
            'personal_info_items': personal_info_items,
            'emergency_items': emergency_items,
            'citizenship_items': citizenship_items,
            'visa_items': visa_items,
            'location_items': location_items,
        }
        return request.render('employee_self_service.portal_my_personal_details', values)

    @http.route(['/my/time-off', '/my/time-off/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_timeoff(self, page=1, sortby=None, filterby=None, **kw):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        searchbar_sortings = {
            'date': {'label': _('From Date'), 'order': 'request_date_from desc, id desc'},
            'status': {'label': _('Status'), 'order': 'state asc, request_date_from desc'},
        }
        sortby = sortby or 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'to_approve': {'label': _('To Approve'), 'domain': [('state', 'in', ['confirm', 'validate1'])]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'validate')]},
            'refused': {'label': _('Refused'), 'domain': [('state', '=', 'refuse')]},
        }
        filterby = filterby or 'all'
        domain = [('employee_id', '=', employee.id)] + searchbar_filters[filterby]['domain']

        leave_model = request.env['hr.leave'].sudo()
        leave_count = leave_model.search_count(domain)
        pager = portal_pager(
            url='/my/time-off',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=leave_count,
            page=page,
            step=10
        )
        leaves = leave_model.search(domain, order=order, limit=10, offset=pager['offset'])

        leave_types = self._get_portal_allowed_leave_types(employee)
        timeoff_dashboard = {
            'total': request.env['hr.leave'].sudo().search_count([('employee_id', '=', employee.id)]),
            'to_approve': request.env['hr.leave'].sudo().search_count([('employee_id', '=', employee.id), ('state', 'in', ['confirm', 'validate1'])]),
            'approved': request.env['hr.leave'].sudo().search_count([('employee_id', '=', employee.id), ('state', '=', 'validate')]),
            'refused': request.env['hr.leave'].sudo().search_count([('employee_id', '=', employee.id), ('state', '=', 'refuse')]),
        }

        allocation_model = request.env['hr.leave.allocation'].sudo()
        approved_leave_domain_base = [
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
        ]
        allocation_domain_base = [
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
        ]

        balance_cards = []
        ordered_types = leave_types.sorted(key=lambda lt: (lt.sequence, lt.id))

        def _sum_existing_days(records):
            for field_name in ('number_of_days_display', 'number_of_days', 'number_of_days_temp'):
                if field_name in records._fields:
                    return sum(records.mapped(field_name) or [0.0])
            return 0.0

        def _leave_type_unit(leave_type):
            request_unit = getattr(leave_type, 'request_unit', False)
            if request_unit == 'hour':
                return 'hours'
            if request_unit == 'half_day':
                return 'days'
            if request_unit:
                return 'days'
            if 'take_time_off_in' in leave_type._fields:
                take_time_off_in = getattr(leave_type, 'take_time_off_in', False)
                if take_time_off_in == 'hour':
                    return 'hours'
            return 'days'

        for leave_type in ordered_types:
            allocations = allocation_model.search(allocation_domain_base + [('holiday_status_id', '=', leave_type.id)])
            approved_leaves = request.env['hr.leave'].sudo().search(approved_leave_domain_base + [('holiday_status_id', '=', leave_type.id)])
            allocated_days = _sum_existing_days(allocations)
            used_days = _sum_existing_days(approved_leaves)
            validity_dates = [d for d in allocations.mapped('date_to') if d]

            contextual_type = leave_type.with_context(
                employee_id=employee.id,
                default_employee_id=employee.id,
                allowed_company_ids=[employee.company_id.id],
            )

            available_value = False
            for field_name in ('virtual_remaining_leaves', 'remaining_leaves', 'max_leaves'):
                if field_name in contextual_type._fields:
                    field_value = contextual_type[field_name]
                    if field_value not in (False, None):
                        available_value = field_value
                        break

            if available_value in (False, None):
                available_value = max(allocated_days - used_days, 0.0)

            balance_cards.append({
                'name': leave_type.name,
                'days_available': round(available_value or 0.0, 2),
                'valid_until': max(validity_dates) if validity_dates else False,
                'unit': _leave_type_unit(leave_type),
            })

        values = {
            'employee': employee,
            'leaves': leaves,
            'leave_types': leave_types,
            'timeoff_dashboard': timeoff_dashboard,
            'timeoff_balance_cards': balance_cards,
            'page_name': 'timeoff',
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'default_url': '/my/time-off',
            'success': kw.get('success'),
            'error': kw.get('error'),
        }
        return request.render('employee_self_service.portal_my_timeoff', values)

    @http.route(['/my/time-off/create'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_create_timeoff(self, **post):
        employee, redirect = self._redirect_if_no_employee()
        if redirect:
            return redirect

        leave_type_id = int(post.get('leave_type_id') or 0)
        date_from = post.get('date_from')
        date_to = post.get('date_to')
        description = post.get('description') or False
        attachment = request.httprequest.files.get('attachment')

        _logger.info("=== PORTAL CREATE LEAVE DEBUG START ===")
        _logger.info("POST Data: %s", post)
        _logger.info("Employee: %s (%s)", employee.name, employee.id)

        if not leave_type_id or not date_from or not date_to:
            _logger.warning("Create leave failed: missing required fields")
            return request.redirect('/my/time-off?error=missing')

        if date_to < date_from:
            _logger.warning("Create leave failed: invalid date range | from=%s | to=%s", date_from, date_to)
            return request.redirect('/my/time-off?error=range')

        allowed_leave_types = self._get_portal_allowed_leave_types(employee)
        _logger.info("Allowed leave type IDs on submit: %s", allowed_leave_types.ids)

        leave_type = allowed_leave_types.filtered(lambda lt: lt.id == leave_type_id)
        if not leave_type:
            _logger.warning(
                "Create leave failed: selected leave type %s is not allowed for employee %s",
                leave_type_id, employee.name
            )
            _logger.info("=== PORTAL CREATE LEAVE DEBUG END ===")
            return request.redirect('/my/time-off?error=type')

        leave_type = leave_type[0]

        vals = {
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'name': description or _('Time Off Request'),
        }

        _logger.info("Creating leave with vals: %s", vals)

        try:
            leave = request.env['hr.leave'].sudo().with_context(
                allowed_company_ids=[employee.company_id.id],
                default_employee_id=employee.id,
                employee_id=employee.id,
            ).create(vals)

            if attachment and attachment.filename:
                request.env['ir.attachment'].sudo().create({
                    'name': attachment.filename,
                    'type': 'binary',
                    'datas': base64.b64encode(attachment.read()),
                    'res_model': 'hr.leave',
                    'res_id': leave.id,
                    'mimetype': attachment.mimetype,
                })

            _logger.info(
                "Leave created successfully | ID=%s | Type=%s | State=%s | Employee=%s",
                leave.id, leave.holiday_status_id.name, leave.state, leave.employee_id.name
            )
        except Exception as e:
            _logger.exception("Create leave failed with exception: %s", e)
            _logger.info("=== PORTAL CREATE LEAVE DEBUG END ===")
            return request.redirect('/my/time-off?error=type')

        _logger.info("=== PORTAL CREATE LEAVE DEBUG END ===")
        return request.redirect('/my/time-off?success=1')