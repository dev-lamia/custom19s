# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZkAttendancePullWizard(models.TransientModel):
    _name = "zk.attendance.pull.wizard"
    _description = "Queue a ZKTeco Attendance Pull"

    device_id = fields.Many2one("zk.device", required=True, readonly=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    batch_days = fields.Integer(
        string="Device Request Range (Days)", default=7, required=True,
        help="For reliability, long attendance periods are requested in smaller sections. For example, 7 requests up to seven days at a time and does not change the dates selected above.",
    )

    def action_queue(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("End date must be on or after the start date."))
        if not 1 <= self.batch_days <= 31:
            raise ValidationError(_("Days per device request must be between 1 and 31."))
        if self.date_to > self.date_from + timedelta(days=365):
            raise ValidationError(_("For safety, queue no more than one year at a time."))

        cursor = self.date_from
        queued = 0
        while cursor <= self.date_to:
            batch_end = min(cursor + timedelta(days=self.batch_days - 1), self.date_to)
            start = datetime.combine(cursor, time.min).strftime("%Y-%m-%dT%H:%M:%S")
            end = datetime.combine(batch_end, time.max).strftime("%Y-%m-%dT%H:%M:%S")
            command = "DATA QUERY ATTLOG StartTime=%s\tEndTime=%s" % (start, end)
            operation = _("Pull attendance: %(start)s to %(end)s", start=cursor, end=batch_end)
            self.device_id.queue_adms_command(command, operation)
            queued += 1
            cursor = batch_end + timedelta(days=1)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Attendance pull queued"),
                "message": _("%(count)s dated request(s) are queued. ADMS sends them one at a time when the terminal polls; watch Command History for Pending, Sent, Done, or Failed.", count=queued),
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
