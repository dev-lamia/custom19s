# -*- coding: utf-8 -*-
import datetime

import pytz

from odoo import fields, models


class ZkBiometricDashboard(models.Model):
    _name = "zk.biometric.dashboard"
    _description = "Biometric Attendance Dashboard"

    name = fields.Char(default="Biometric Attendance", required=True)
    device_count = fields.Integer(compute="_compute_metrics")
    connected_count = fields.Integer(compute="_compute_metrics")
    offline_count = fields.Integer(compute="_compute_metrics")
    device_user_count = fields.Integer(compute="_compute_metrics")
    mapped_count = fields.Integer(compute="_compute_metrics")
    unmapped_count = fields.Integer(compute="_compute_metrics")
    today_punch_count = fields.Integer(compute="_compute_metrics")
    total_punch_count = fields.Integer(compute="_compute_metrics")
    pending_command_count = fields.Integer(compute="_compute_metrics")
    failed_command_count = fields.Integer(compute="_compute_metrics")
    needs_attention_count = fields.Integer(compute="_compute_metrics")
    recent_punch_ids = fields.Many2many("zk.machine.attendance", compute="_compute_metrics", string="Recent Punches")

    def _company_domain(self):
        return [("company_id", "in", self.env.companies.ids)]

    def _today_bounds(self):
        timezone = pytz.timezone(self.env.user.tz or "UTC")
        today = fields.Date.context_today(self)
        start = timezone.localize(datetime.datetime.combine(today, datetime.time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end = timezone.localize(datetime.datetime.combine(today, datetime.time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        return fields.Datetime.to_string(start), fields.Datetime.to_string(end)

    def _compute_metrics(self):
        Device = self.env["zk.device"].sudo()
        DeviceUser = self.env["zk.device.user"].sudo()
        Log = self.env["zk.machine.attendance"].sudo()
        Command = self.env["zk.device.command"].sudo()
        company_domain = self._company_domain()
        start, end = self._today_bounds()
        cutoff = Device._online_cutoff()
        for record in self:
            record.device_count = Device.search_count(company_domain)
            record.connected_count = Device.search_count(company_domain + [("last_seen", ">=", cutoff)])
            record.offline_count = Device.search_count(company_domain + ["|", ("last_seen", "=", False), ("last_seen", "<", cutoff)])
            record.device_user_count = DeviceUser.search_count(company_domain)
            record.mapped_count = DeviceUser.search_count(company_domain + [("employee_id", "!=", False)])
            record.unmapped_count = Log.search_count(company_domain + [("employee_id", "=", False)])
            record.today_punch_count = Log.search_count(company_domain + [("punching_time", ">=", start), ("punching_time", "<=", end)])
            record.total_punch_count = Log.search_count(company_domain)
            record.pending_command_count = Command.search_count(company_domain + [("state", "in", ["pending", "sent"])])
            record.failed_command_count = Command.search_count(company_domain + [("state", "=", "failed")])
            record.needs_attention_count = Device.search_count(company_domain + [("last_seen", "<", cutoff)]) + record.failed_command_count
            record.recent_punch_ids = Log.search(company_domain, order="punching_time desc, id desc", limit=10)

    def _open(self, xmlid, domain=None, context=None):
        action = self.env.ref(xmlid).read()[0]
        if domain is not None:
            action["domain"] = domain
        if context is not None:
            action["context"] = context
        return action

    def action_open_devices(self):
        return self._open("tam_hr_zk_attendance.zk_device_action")

    def action_open_online_devices(self):
        cutoff = self.env["zk.device"]._online_cutoff()
        return self._open("tam_hr_zk_attendance.zk_device_action", [("last_seen", ">=", cutoff)], {"search_default_online": 1})

    def action_open_offline_devices(self):
        cutoff = self.env["zk.device"]._online_cutoff()
        return self._open("tam_hr_zk_attendance.zk_device_action", ["|", ("last_seen", "=", False), ("last_seen", "<", cutoff)], {"search_default_offline": 1})

    def action_open_device_users(self):
        return self._open(
            "tam_hr_zk_attendance.zk_device_user_action",
            [("employee_id", "!=", False)],
            {"search_default_mapped": 1},
        )

    def action_open_unmapped(self):
        return self._open("tam_hr_zk_attendance.machine_attendance_action", [("employee_id", "=", False)])

    def action_open_today(self):
        start, end = self._today_bounds()
        return self._open("tam_hr_zk_attendance.machine_attendance_action", [("punching_time", ">=", start), ("punching_time", "<=", end)], {"search_default_today": 1})

    def action_open_all_logs(self):
        return self._open("tam_hr_zk_attendance.machine_attendance_action")

    def action_open_commands(self):
        return self._open("tam_hr_zk_attendance.zk_device_command_action")
