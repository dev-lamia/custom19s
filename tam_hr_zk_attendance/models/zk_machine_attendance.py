# -*- coding: utf-8 -*-
import hashlib

from odoo import api, fields, models


class ZkMachineAttendance(models.Model):
    """Raw biometric punch model.

    Historical rows are never rewritten merely to enable duplicate protection.
    ``source_event_key`` is nullable so old data remains untouched, while every
    new raw punch gets a deterministic fingerprint that makes device/Odoo
    retransmissions idempotent.
    """

    _name = "zk.machine.attendance"
    _description = "ZK Machine Attendance Log"
    _order = "punching_time desc"

    _zk_source_event_key_unique = models.Constraint(
        "UNIQUE (source_event_key)",
        "This exact biometric device event has already been received.",
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        index=True,
        ondelete="set null",
        help="Mapped employee. Empty means the biometric PIN has not been mapped yet.",
    )
    device_id = fields.Many2one(
        "zk.device",
        string="Device",
        index=True,
        ondelete="set null",
    )
    device_id_num = fields.Char(
        string="Biometric Device ID",
        required=True,
        index=True,
        help="User/PIN ID received from the biometric device.",
    )
    device_user_id = fields.Many2one(
        "zk.device.user",
        string="Device User (Exact Device + PIN)",
        compute="_compute_device_user_id",
        compute_sudo=True,
        store=True,
        readonly=True,
        index=True,
        ondelete="set null",
        help=(
            "Stored grouping key for the Device User matching this exact device "
            "and PIN. This never changes the employee mapping or raw punch."
        ),
    )

    @api.depends("device_id", "device_id_num")
    def _compute_device_user_id(self):
        """Resolve a groupable Device User, never by global PIN alone.

        The name shown by this relation is live, not a stored punch-time name.
        The post-migration backfills existing raw punches on module upgrade;
        newly created Device Users reconcile pre-existing logs separately.
        """
        devices = self.mapped("device_id").ids
        pins = list({str(rec.device_id_num).strip() for rec in self if rec.device_id_num})
        users_by_pair = {}
        if devices and pins:
            users = self.env["zk.device.user"].sudo().search([
                ("device_id", "in", devices),
                ("pin", "in", pins),
            ])
            users_by_pair = {(u.device_id.id, u.pin): u.id for u in users}
        for record in self:
            record.device_user_id = users_by_pair.get((
                record.device_id.id,
                str(record.device_id_num or "").strip(),
            ), False)

    device_user_name = fields.Char(
        string="Device User Name",
        compute="_compute_device_user_name",
        compute_sudo=True,
        readonly=True,
        help=(
            "Name currently reported for this exact device and PIN in Device Users. "
            "It may be blank if the device has not supplied a name; it is not "
            "a historical snapshot and does not change the raw punch or employee mapping."
        ),
    )

    @api.depends("device_id", "device_id_num")
    def _compute_device_user_name(self):
        """Show the terminal's name without trusting an employee-wide PIN.

        The raw-log operator may not have general access to Device Users. The
        sudo lookup is limited to device/PIN pairs on attendance records the
        caller is already authorized to read; only the non-sensitive name is
        exposed. Fetch all pairs in one query for paginated lists.
        """
        devices = self.mapped("device_id").ids
        pins = list({str(rec.device_id_num).strip() for rec in self if rec.device_id_num})
        names = {}
        if devices and pins:
            users = self.env["zk.device.user"].sudo().search([
                ("device_id", "in", devices),
                ("pin", "in", pins),
            ])
            names = {
                (user.device_id.id, user.pin): user.name or False
                for user in users
            }
        for record in self:
            record.device_user_name = names.get((
                record.device_id.id,
                str(record.device_id_num or "").strip(),
            ), False)

    punch_type = fields.Selection(
        [
            ("0", "Check In"),
            ("1", "Check Out"),
            ("2", "Break Out"),
            ("3", "Break In"),
            ("4", "Overtime In"),
            ("5", "Overtime Out"),
            ("255", "Other / Duplicate"),
        ],
        string="Punching Type",
        required=True,
        index=True,
        help="Punch/status value received from the device.",
    )
    attendance_type = fields.Selection(
        [
            ("0", "Auto / Mixed"),
            ("1", "Finger"),
            ("2", "User ID / Type 2"),
            ("3", "Password"),
            ("4", "Card"),
            ("5", "Finger or Password"),
            ("6", "Finger or Card"),
            ("15", "Face"),
            ("20", "Face + Finger"),
            ("25", "Palm"),
            ("255", "Other / Duplicate"),
        ],
        string="Category",
        help="Verification method received from the device when supported.",
    )
    punching_time = fields.Datetime(
        string="Punching Time",
        required=True,
        index=True,
        help="Punch time stored in UTC in Odoo.",
    )
    source_event_key = fields.Char(
        string="Source Event Key",
        readonly=True,
        copy=False,
        index=True,
        help=(
            "Internal idempotency fingerprint for newly received biometric events. "
            "Historical records may intentionally have this field empty."
        ),
    )
    @api.model
    def _make_source_event_key(self, device_id, device_id_num, punching_time, punch_type):
        """Return a deterministic key for one physical biometric event."""
        if not device_id or not str(device_id_num or "").strip() or punching_time in (False, None) or punch_type in (False, None):
            return False
        dt = fields.Datetime.to_datetime(punching_time)
        canonical_dt = fields.Datetime.to_string(dt)
        payload = "%s|%s|%s|%s" % (
            int(device_id),
            str(device_id_num).strip(),
            canonical_dt,
            str(punch_type).strip(),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        # Only NEW rows receive an event key. Existing historical rows are never
        # backfilled by upgrade, avoiding any destructive historical cleanup.
        prepared = []
        for original_vals in vals_list:
            vals = dict(original_vals)
            if not vals.get("source_event_key"):
                vals["source_event_key"] = self._make_source_event_key(
                    vals.get("device_id"),
                    vals.get("device_id_num"),
                    vals.get("punching_time"),
                    vals.get("punch_type"),
                )
            prepared.append(vals)
        return super().create(prepared)


    @api.model
    def _zk_upsert_received_punch(self, vals):
        """Idempotently store one inbound event, including pre-key historical rows.

        Identity is (device, PIN, UTC second, punch type); verification mode
        is metadata and is deliberately excluded. Never reassign an already
        mapped punch merely because today's device-user mapping has changed:
        the correction wizard is the audited way to correct old mappings.

        Returns (record, created, enriched). No existing punch is deleted.
        The savepoint allows concurrent workers to race against the nullable
        unique event key without breaking the HTTP transaction.
        """
        domain = [
            ("device_id", "=", vals["device_id"]),
            ("device_id_num", "=", vals["device_id_num"]),
            ("punching_time", "=", vals["punching_time"]),
            ("punch_type", "=", vals["punch_type"]),
        ]
        record = self.search(domain, order="id asc", limit=1)
        if not record:
            try:
                with self.env.cr.savepoint():
                    record = self.create(vals)
                return record, True, False
            except Exception:
                # Another request may have inserted the same event just now.
                # Reraise unrelated errors instead of swallowing them.
                record = self.search(domain, order="id asc", limit=1)
                if not record:
                    raise

        updates = {}
        if vals.get("employee_id") and not record.employee_id:
            updates["employee_id"] = vals["employee_id"]
        if vals.get("attendance_type") and not record.attendance_type:
            updates["attendance_type"] = vals["attendance_type"]
        if updates:
            record.write(updates)
        return record, False, bool(updates)
