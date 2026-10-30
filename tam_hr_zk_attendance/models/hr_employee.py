# -*- coding: utf-8 -*-
from datetime import timedelta

import pytz

from odoo import api, fields, models


_HR_EMPLOYEE_FIELD_GROUP = "hr.group_hr_user"
_BIOMETRIC_MANAGER_GROUP = "tam_hr_zk_attendance.group_biometric_manager"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    device_id_num = fields.Char(
        string="Employee ID",
        copy=False,
        groups=_HR_EMPLOYEE_FIELD_GROUP,
        help="Organisation employee identifier retained for compatibility with related modules. It is not a biometric device PIN.",
    )

    device_user_id = fields.Char(
        related="device_id_num",
        string="Employee ID",
        readonly=False,
        groups=_HR_EMPLOYEE_FIELD_GROUP,
        help="Compatibility alias for the organisation Employee ID. Device and PIN mappings remain device-specific.",
    )

    biometric_device_name = fields.Char(
        string="Biometric Device Display Name",
        groups=_HR_EMPLOYEE_FIELD_GROUP,
    )

    def _zk_attendance_timezone(self):
        """One employee timezone for biometric days, HR display and lunch policy.

        The employee's work calendar takes priority over the logged-in HR
        viewer and the terminal's timezone. Always return a pytz tzinfo.
        """
        self.ensure_one()
        names = (
            self.resource_calendar_id.tz,
            self.user_id.tz if self.user_id else False,
            self.company_id.resource_calendar_id.tz,
            "UTC",
        )
        for name in names:
            if name:
                try:
                    return pytz.timezone(name)
                except pytz.UnknownTimeZoneError:
                    continue
        return pytz.UTC

    def _zk_workday_date(self, utc_timestamp):
        """Assign a punch to the employee's local workday, incl. split night shifts.

        When the schedule has an evening segment ending at midnight followed
        by an early-morning segment, the next morning belongs to the prior
        workday. Otherwise use the employee-local calendar date.
        """
        self.ensure_one()
        dt = fields.Datetime.to_datetime(utc_timestamp)
        tz = self._zk_attendance_timezone()
        if not dt.tzinfo:
            dt = pytz.UTC.localize(dt)
        local = dt.astimezone(tz)
        day = local.date()
        if local.hour >= 12 or not self.resource_calendar_id:
            return day
        previous = day - timedelta(days=1)
        lines = self.resource_calendar_id.attendance_ids.filtered(
            lambda line: line.day_period != "break"
        )
        previous_night = any(
            line.dayofweek == str(previous.weekday())
            and line.hour_from >= 17.0 and line.hour_to >= 23.5
            for line in lines
        )
        today_morning = any(
            line.dayofweek == str(day.weekday())
            and line.hour_from <= 0.5 and line.hour_to <= 12.0
            and local.hour + local.minute / 60.0 <= line.hour_to + 1.0
            for line in lines
        )
        return previous if previous_night and today_morning else day


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    device_id_num = fields.Char(
        string="Employee ID",
        compute="_compute_public_device_id_num",
        readonly=True,
    )

    device_user_id = fields.Char(
        related="employee_id.device_user_id",
        string="Employee ID",
        readonly=True,
        groups=_BIOMETRIC_MANAGER_GROUP,
    )

    @api.depends("employee_id")
    @api.depends_context("uid")
    def _compute_public_device_id_num(self):
        """Expose an Employee ID only to the employee it belongs to.

        This public-model field lets standard employees open their own
        appraisal/profile without reading biometric metadata on private
        ``hr.employee`` records or other employees' identifiers.
        """
        own_employee_ids = set(self.env.user.employee_ids.ids)
        for employee in self:
            employee.device_id_num = (
                employee.employee_id.sudo().device_id_num
                if employee.id in own_employee_ids
                else False
            )
