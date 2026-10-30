# -*- coding: utf-8 -*-
import datetime
import logging

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


def _zk_supported_checkout_mode(mode_field, env):
    """Read a native selection without assuming optional enterprise values."""
    if not mode_field or not hasattr(mode_field, "get_values"):
        return False
    choices = set(mode_field.get_values(env))
    if "auto_check_out" in choices:
        return "auto_check_out"
    return "manual" if "manual" in choices else False


class ZkDeviceHardening(models.Model):
    _name = "zk.device"
    _inherit = ["zk.device", "mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(string="Device Name", required=True, tracking=True)
    address_id = fields.Char(string="Location", tracking=True)
    tz = fields.Selection(selection=lambda self: self.env["res.users"].fields_get(["tz"])["tz"]["selection"], string="Timezone", tracking=True)
    allow_push = fields.Boolean(string="Receive Attendance", tracking=True)
    serial_number = fields.Char(string="Serial Number", index=True, copy=False, readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    is_approved = fields.Boolean(string="Approved Device", default=False, tracking=True)
    connection_status = fields.Selection(
        [("online", "Online"), ("offline", "Offline")],
        string="ADMS Status", compute="_compute_connection_status",
        search="_search_connection_status", readonly=True,
    )

    @api.model
    def _search_connection_status(self, operator, value):
        cutoff = self._online_cutoff()
        online_domain = [("last_seen", ">=", cutoff)]
        offline_domain = ["|", ("last_seen", "=", False), ("last_seen", "<", cutoff)]
        # In Odoo 19 the domain optimizer can pass an OrderedSet for a
        # selection filter. Keep it iterable rather than using it as a set
        # member, because OrderedSet itself is intentionally unhashable.
        if isinstance(value, str):
            statuses = (value,)
        else:
            try:
                statuses = tuple(value)
            except TypeError:
                statuses = (value,)

        online_requested = "online" in statuses
        offline_requested = "offline" in statuses
        if operator in ("=", "==", "in"):
            if online_requested and not offline_requested:
                return online_domain
            if offline_requested and not online_requested:
                return offline_domain
            if online_requested and offline_requested:
                return []
        if operator in ("!=", "<>", "not in"):
            if online_requested and not offline_requested:
                return offline_domain
            if offline_requested and not online_requested:
                return online_domain
        return [("id", "=", 0)]
    _zk_device_serial_unique = models.Constraint("UNIQUE(serial_number)", "A biometric device serial number must be unique.")


class ZkDeviceUserCompany(models.Model):
    _inherit = "zk.device.user"
    _check_company_auto = True
    company_id = fields.Many2one(related="device_id.company_id", store=True, index=True, readonly=True)
    device_location = fields.Char(related="device_id.address_id", store=True, index=True, readonly=True)
    # Device ownership controls access to the device/PIN record; the employee
    # can belong to a different company if the linking manager is authorized
    # for BOTH companies. Odoo's automatic same-company constraint does not
    # express this business rule, so validate explicit mapping edits below.
    employee_id = fields.Many2one("hr.employee", check_company=False)
    # Public HR proxy for the Device User editor. The real mapping remains the
    # existing employee_id field; no private HR ACL is granted to managers.
    employee_public_id = fields.Many2one(
        "hr.employee.public", string="Employee (Public Directory)",
        compute="_compute_employee_public_id", inverse="_inverse_employee_public_id",
        readonly=False, compute_sudo=False,
    )
    eligible_employee_company_ids = fields.Many2many(
        "res.company", compute="_compute_eligible_employee_company_ids",
        compute_sudo=False, string="Permitted Employee Companies",
    )

    @api.depends("employee_id")
    def _compute_employee_public_id(self):
        for record in self:
            record.employee_public_id = record.employee_id.id or False

    def _inverse_employee_public_id(self):
        for record in self:
            # Reuse the same server-side checks as direct employee_id edits.
            record.write({"employee_id": record.employee_public_id.id or False})

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_eligible_employee_company_ids(self):
        allowed = self.env.user.company_ids
        for record in self:
            record.eligible_employee_company_ids = allowed

    def _check_employee_mapping_access(self, employee_id):
        """Enforce both-company rights without changing the module's ACLs.

        Record rules still control access to the owning device and device user.
        The employee must also be visible through the public HR directory, so
        a crafted RPC cannot link an employee the manager cannot see.
        """
        if not employee_id:
            return
        user = self.env.user
        authorized_companies = user.company_ids.ids
        if not authorized_companies:
            raise AccessError(_("You have no permitted company for employee mapping."))
        Public = self.env["hr.employee.public"].with_context(
            allowed_company_ids=authorized_companies
        )
        visible = Public.search([("id", "=", employee_id)], limit=1)
        if not visible or not visible.company_id or visible.company_id.id not in authorized_companies:
            raise AccessError(_("You cannot link an employee outside your permitted companies."))
        for record in self:
            if record.device_id.company_id.id not in authorized_companies:
                raise AccessError(_("You cannot change a device user outside your permitted companies."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id"):
                device = self.env["zk.device"].browse(vals.get("device_id"))
                self.browse()._check_employee_mapping_access(vals["employee_id"])
                if device.company_id.id not in self.env.user.company_ids.ids:
                    raise AccessError(_("You cannot map a device in another company."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("employee_id"):
            self._check_employee_mapping_access(vals["employee_id"])
        return super().write(vals)


class ZkDeviceCommandCompany(models.Model):
    _inherit = "zk.device.command"
    _check_company_auto = True
    company_id = fields.Many2one(related="device_id.company_id", store=True, index=True, readonly=True)
    device_location = fields.Char(related="device_id.address_id", store=True, index=True, readonly=True)


class ZkMachineAttendanceCompany(models.Model):
    _inherit = "zk.machine.attendance"
    _check_company_auto = True
    company_id = fields.Many2one(related="device_id.company_id", store=True, index=True, readonly=True)
    device_location = fields.Char(related="device_id.address_id", store=True, index=True, readonly=True)
    # Raw evidence belongs to the physical device company, even when its
    # mapped employee is employed in another permitted company. Derived
    # hr.attendance records retain their employee-centric company behavior.
    employee_id = fields.Many2one("hr.employee", check_company=False)


class ZkDeviceFingerprintCompany(models.Model):
    _inherit = "zk.device.fingerprint"
    _check_company_auto = True
    company_id = fields.Many2one(related="device_id.company_id", store=True, index=True, readonly=True)


class ZkDeviceBiometricTemplateCompany(models.Model):
    _inherit = "zk.device.biometric.template"
    _check_company_auto = True
    company_id = fields.Many2one(related="device_id.company_id", store=True, index=True, readonly=True)


class HrAttendanceBiometricProvenance(models.Model):
    _inherit = "hr.attendance"

    biometric_generated = fields.Boolean(string="Generated from Biometric Device", readonly=True, copy=False, index=True)
    biometric_device_id = fields.Many2one("zk.device", string="Biometric Source Device", readonly=True, copy=False, index=True)
    biometric_pin = fields.Char(string="Biometric Source PIN", readonly=True, copy=False, index=True)


    @api.model
    def _zk_zero_hour_checkout_values(self, attendance):
        """Use only native checkout modes actually supported by this database.

        Do not declare/extend ``out_mode``: Enterprise, Community and custom
        attendance modules can supply different selections (or no field).
        """
        vals = {"check_out": fields.Datetime.to_string(attendance.check_in)}
        mode = _zk_supported_checkout_mode(self._fields.get("out_mode"), self.env)
        if mode:
            vals["out_mode"] = mode
        return vals

    @api.model
    def _zk_genuine_checkout_values(self, check_out):
        """Real device checkout supersedes an earlier zero-hour placeholder."""
        vals = {"check_out": fields.Datetime.to_string(check_out)}
        field = self._fields.get("out_mode")
        if field and hasattr(field, "get_values") and "manual" in field.get_values(self.env):
            vals["out_mode"] = "manual"
        return vals

    @api.model
    def _zk_close_previous_open_attendance(self, employee_id, next_check_in_utc, device_timezone):
        """Close a *previous local day*'s proven biometric open attendance.

        The next check-in is only a trigger; the checkout equals the ORIGINAL
        check-in, producing exactly zero worked hours. Never change manual or
        unknown-provenance records. All employee devices are considered because
        the same employee may check in at a different device the next day.

        Called chronologically by both the ADMS receiver and rebuild wizard.
        It is deliberately idempotent: already closed records stay unchanged.
        """
        utc_dt = fields.Datetime.to_datetime(next_check_in_utc)
        local_day = pytz.utc.localize(utc_dt).astimezone(device_timezone).date()
        local_start = device_timezone.localize(
            datetime.datetime.combine(local_day, datetime.time.min)
        )
        day_start_utc = fields.Datetime.to_string(
            local_start.astimezone(pytz.utc).replace(tzinfo=None)
        )
        old_open = self.search([
            ("employee_id", "=", employee_id),
            ("check_out", "=", False),
            ("check_in", "<", day_start_utc),
        ], order="check_in asc", limit=1)
        if not old_open:
            return False
        # Provenance is mandatory: no alterations to manual attendance or an
        # old database record whose source cannot be established.
        if not (old_open.biometric_generated and old_open.biometric_device_id and old_open.biometric_pin):
            raise ValidationError(_(
                "Cannot process the next biometric check-in: %(employee)s has an "
                "older open attendance (%(attendance)s) without verified biometric "
                "provenance. Review it manually; no attendance was auto-closed.",
                employee=old_open.employee_id.name,
                attendance=old_open.check_in,
            ))
        vals = self._zk_zero_hour_checkout_values(old_open)
        old_open.write(vals)
        _logger.info(
            "ZK closed prior-day biometric attendance at original check-in "
            "(employee_id=%s attendance_id=%s check_out=%s out_mode=%s)",
            employee_id, old_open.id, vals["check_out"], vals.get("out_mode"),
        )
        return old_open


    @api.model
    def _zk_sync_employee_day(self, employee_id, work_date, *, finalize_missing=True):
        """Reconcile exactly one employee/workday across all mapped device PINs.

        History is deliberately NOT migrated by module installation. On live
        events, only a SINGLE proven biometric attendance may be updated;
        unproven/manual rows and pre-existing duplicate days are conflicts.
        An employee may have different PINs on different devices, and different
        employees may share one PIN on different devices.
        """
        employee = self.env["hr.employee"].sudo().browse(employee_id).exists()
        if not employee:
            return "unchanged"
        if isinstance(work_date, str):
            work_date = datetime.date.fromisoformat(work_date)
        tz = employee._zk_attendance_timezone()

        # Serialize competing ADMS requests for one employee/day; duplicates
        # cannot both decide there is no matching hr.attendance in parallel.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            (int(employee_id), int(work_date.toordinal())),
        )
        search_begin = tz.localize(datetime.datetime.combine(
            work_date - datetime.timedelta(days=1), datetime.time.min
        )).astimezone(pytz.UTC).replace(tzinfo=None)
        search_end = tz.localize(datetime.datetime.combine(
            work_date + datetime.timedelta(days=2), datetime.time.min
        )).astimezone(pytz.UTC).replace(tzinfo=None)
        logs = self.env["zk.machine.attendance"].sudo().search([
            ("employee_id", "=", employee_id),
            ("punching_time", ">=", fields.Datetime.to_string(search_begin)),
            ("punching_time", "<", fields.Datetime.to_string(search_end)),
        ], order="punching_time asc, id asc")
        day_logs = logs.filtered(
            lambda log: employee._zk_workday_date(log.punching_time) == work_date
        )
        if not day_logs:
            return "unchanged"

        first_log, last_log = day_logs[0], day_logs[-1]
        first = fields.Datetime.to_datetime(first_log.punching_time)
        last = fields.Datetime.to_datetime(last_log.punching_time)
        # The agreed policy uses first and last PUNCH, not punch_type. Two
        # distinct timestamps are enough; an isolated completed day is zero-hour.
        has_checkout = last > first
        completed = work_date < fields.Date.context_today(
            employee.with_context(tz=str(tz))
        )
        checkout = last if has_checkout else (first if finalize_missing and completed else False)

        # Odoo's one-open-attendance rule also applies when the next check-in
        # comes from a different device/PIN. Never close manual unknown history.
        self._zk_close_previous_open_attendance(employee_id, first, tz)

        local_start = tz.localize(datetime.datetime.combine(work_date, datetime.time.min))
        local_stop = tz.localize(datetime.datetime.combine(
            work_date + datetime.timedelta(days=1), datetime.time.min
        ))
        start = fields.Datetime.to_string(local_start.astimezone(pytz.UTC).replace(tzinfo=None))
        stop = fields.Datetime.to_string(local_stop.astimezone(pytz.UTC).replace(tzinfo=None))

        # Include records crossing midnight as well as all devices and PINs.
        # The candidate must belong to this workday; a prior shift crossing
        # midnight is an overlap conflict and never silently absorbed.
        overlapping = self.search([
            ("employee_id", "=", employee_id),
            ("check_in", "<", stop),
            "|", ("check_out", "=", False), ("check_out", ">=", start),
        ], order="check_in asc, id asc").filtered(
            # Yesterday's night shift can validly finish this morning;
            # it must not block today's later, nonoverlapping shift.
            lambda att: (
                employee._zk_workday_date(att.check_in) == work_date
                or not att.check_out
                or fields.Datetime.to_datetime(att.check_out) >= first
            )
        )
        if len(overlapping) > 1:
            _logger.warning(
                "ZK HR sync conflict: multiple existing attendance records for "
                "employee_id=%s workday=%s ids=%s; historical cleanup is manual",
                employee_id, work_date, overlapping.ids,
            )
            return "conflict"
        existing = overlapping[:1]
        if existing:
            existing_start = fields.Datetime.to_datetime(existing.check_in)
            if employee._zk_workday_date(existing_start) != work_date:
                _logger.warning(
                    "ZK HR overlap conflict: employee_id=%s date=%s attendance_id=%s",
                    employee_id, work_date, existing.id,
                )
                return "conflict"
            if not existing.biometric_generated:
                if (existing_start == first and (
                    (not checkout and not existing.check_out) or
                    (checkout and existing.check_out and
                     fields.Datetime.to_datetime(existing.check_out) == checkout)
                )):
                    return "unchanged"
                _logger.warning(
                    "ZK HR sync conflict: unproven attendance preserved "
                    "employee_id=%s date=%s attendance_id=%s",
                    employee_id, work_date, existing.id,
                )
                return "conflict"
            vals = {}
            old_checkout = fields.Datetime.to_datetime(existing.check_out) if existing.check_out else False
            # Never shrink pre-existing biometric data on a partial upload.
            # Earlier/later verified raw scans expand the employee interval;
            # historical changes remain exclusively for the later shell fix.
            if first < existing_start:
                vals["check_in"] = fields.Datetime.to_string(first)
            if checkout and (not old_checkout or checkout > old_checkout):
                if has_checkout or (old_checkout and last > existing_start):
                    vals.update(self._zk_genuine_checkout_values(checkout))
                elif old_checkout:
                    # An earlier first punch makes the prior zero-hour first
                    # punch a genuine last punch, despite a partial upload.
                    vals.update(self._zk_genuine_checkout_values(old_checkout))
                else:
                    vals.update(self._zk_zero_hour_checkout_values(existing))
                    if "check_in" in vals:
                        vals["check_out"] = vals["check_in"]
            # Also expand a zero-hour placeholder when an earlier raw first
            # arrives: original check-in still serves as the last scan.
            if first < existing_start and old_checkout == existing_start:
                vals.update(self._zk_genuine_checkout_values(
                    max(old_checkout, last)
                ))
            if first < existing_start:
                # The first device/PIN in HR provenance is the earliest
                # verified raw punch only when we actually move check-in.
                if existing.biometric_device_id.id != first_log.device_id.id:
                    vals["biometric_device_id"] = first_log.device_id.id
                if existing.biometric_pin != first_log.device_id_num:
                    vals["biometric_pin"] = first_log.device_id_num
            if vals:
                existing.write(vals)
                return "updated"
            return "unchanged"

        vals = {
            "employee_id": employee_id,
            "check_in": fields.Datetime.to_string(first),
            "biometric_generated": True,
            "biometric_device_id": first_log.device_id.id,
            "biometric_pin": first_log.device_id_num,
        }
        if checkout:
            vals["check_out"] = fields.Datetime.to_string(checkout)
        self.create(vals)
        return "created"

    @api.model
    def _zk_sync_local_day(self, employee_id, device, pin, day_logs, device_timezone,
                           *, finalize_missing=True):
        """Compatibility entry point; reconcile WHOLE employee day, not source PIN.

        Older callers (including historical mapping tools) keep this signature.
        The passed device/PIN and logs only identify which employee/day to touch.
        """
        if not day_logs:
            return "unchanged"
        employee = self.env["hr.employee"].sudo().browse(employee_id).exists()
        if not employee:
            return "unchanged"
        date = employee._zk_workday_date(day_logs[0].punching_time)
        return self._zk_sync_employee_day(
            employee_id, date, finalize_missing=finalize_missing,
        )
