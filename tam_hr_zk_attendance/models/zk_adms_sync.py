# -*- coding: utf-8 -*-
from datetime import timedelta
import logging
"""Persistence for ADMS user, template, and command synchronization.

Device Users and safe Command History fields are exposed to Biometric Managers.
Fingerprint/generic biometric template values remain private protocol data and
are never rendered in normal Odoo views or logs.
"""

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class ZkDeviceUser(models.Model):
    _name = "zk.device.user"
    _description = "ZK Device User (ADMS)"
    _rec_name = "pin"
    _order = "device_id, pin"
    _active_name = "active"

    device_id = fields.Many2one("zk.device", required=True, ondelete="cascade", index=True)
    employee_id = fields.Many2one("hr.employee", string="Mapped Employee", ondelete="set null", index=True, help="Employee matched for this PIN on this specific device.")
    pin = fields.Char(required=True, index=True)
    name = fields.Char()
    privilege = fields.Integer(default=0)
    password = fields.Char(copy=False)
    card = fields.Char(copy=False)
    group_id = fields.Char()
    timezone = fields.Char()
    active = fields.Boolean(
        default=True, index=True,
        help="Archive this local cache record after the person was removed manually from the physical terminal. This never sends a device command.",
    )
    updated_at = fields.Datetime(readonly=True)
    image_1920 = fields.Image(string="Profile Picture", max_width=1920, max_height=1920, copy=False)

    _zk_device_user_pin_uniq = models.Constraint(
        "UNIQUE(device_id, pin)", "A PIN must be unique per device."
    )

    @api.depends("name", "pin", "device_id.serial_number")
    def _compute_display_name(self):
        """Distinguish same-name/same-PIN device users in attendance groups."""
        for user in self:
            label = user.name or "Unnamed Device User"
            pin = user.pin or "?"
            serial = user.device_id.serial_number or "Unknown Device"
            user.display_name = "%s (PIN %s / %s)" % (label, pin, serial)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        # A device can upload punches before it uploads its user inventory.
        # Recompute only the newly identified (device, PIN) groups; do not
        # touch employee_id, attendance times, or HR attendance history.
        Raw = self.env["zk.machine.attendance"].sudo()
        field = Raw._fields["device_user_id"]
        needs_recompute = False
        for user in users:
            if not user.device_id or not user.pin:
                continue
            unmatched = Raw.search([
                ("device_id", "=", user.device_id.id),
                ("device_id_num", "=", user.pin),
                ("device_user_id", "=", False),
            ])
            if unmatched:
                self.env.add_to_compute(field, unmatched)
                needs_recompute = True
        # Recompute the grouped key through the ORM so the field cache and
        # computed dependencies remain consistent within the transaction.
        if needs_recompute:
            Raw._recompute_recordset()
        return users
    def write(self, values):
        for record in self:
            if "pin" in values and str(values["pin"] or "").strip() != record.pin:
                raise ValidationError("A device PIN cannot be changed after creation.")
            if "device_id" in values and values["device_id"] != record.device_id.id:
                raise ValidationError("A device user cannot be moved to another device.")
        return super().write(values)

    def action_archive_local(self):
        """Archive only Odoo's cached device user; do not contact the terminal."""
        self._check_local_cache_lifecycle()
        self.write({"active": False})
        return True

    def action_delete_local(self):
        """Permanently remove an already archived cache record, never device data."""
        self._check_local_cache_lifecycle(require_archived=True)
        self.sudo().unlink()
        return {"type": "ir.actions.act_window_close"}

    def _check_local_cache_lifecycle(self, require_archived=False):
        if not (self.env.is_superuser() or self.env.user.has_group(
                "tam_hr_zk_attendance.group_biometric_manager")):
            raise AccessError("Only Biometric Managers may archive or delete local device-user cache records.")
        permitted = self.env.user.company_ids.ids
        Command = self.env["zk.device.command"].sudo()
        for record in self:
            if record.device_id.company_id.id not in permitted:
                raise AccessError("Access to the device company is required.")
            if require_archived and record.active:
                raise UserError("Archive this local cache record before permanently deleting it.")
            if Command.search_count([
                ("device_id", "=", record.device_id.id),
                ("transfer_source_user_id", "=", record.id),
                ("state", "in", ["pending", "sent"]),
            ]):
                raise UserError("Finish or cancel pending transfers before changing this local cache record.")



    @api.model
    def upsert_from_adms(self, device, vals):
        values = {
            "name": vals.get("name") or False,
            "privilege": int(vals.get("pri") or vals.get("privilege") or 0),
            "password": vals.get("passwd") or vals.get("password") or False,
            "card": vals.get("card") or False,
            "group_id": vals.get("grp") or vals.get("group") or False,
            "timezone": vals.get("tz") or False,
            "updated_at": fields.Datetime.now(),
            # An actual device response is authoritative for this local cache.
            "active": True,
        }
        record = self.search([("device_id", "=", device.id), ("pin", "=", vals["pin"])], limit=1)
        if record:
            record.write(values)
        else:
            values.update({"device_id": device.id, "pin": vals["pin"]})
            record = self.create(values)
        # A transfer does not guess a new employee from a matching PIN.
        # Only a successfully acknowledged profile plus a confirmed device
        # user inventory, with matching identity, can apply its stored intent.
        if not record.employee_id:
            # The newest intent wins. A later failed/pending profile must not
            # accidentally reuse an earlier successful transfer's mapping.
            transfer = self.env["zk.device.command"].sudo().search([
                ("device_id", "=", device.id),
                ("transfer_pin", "=", record.pin),
                ("transfer_employee_id", "!=", False),
            ], order="id desc", limit=1)
            if transfer:
                transfer._zk_apply_transfer_mapping(target_user=record)
        return record


class ZkDeviceBiometricTemplate(models.Model):
    """Private extensible cache. Only fingerprint protocol is currently verified."""
    _name = "zk.device.biometric.template"
    _description = "Private Biometric Template Cache"
    _order = "device_id, pin, biometric_type, template_index"

    device_id = fields.Many2one("zk.device", required=True, ondelete="cascade", index=True)
    pin = fields.Char(required=True, index=True)
    biometric_type = fields.Selection([("fingerprint", "Fingerprint"), ("face", "Face"), ("palm", "Palm"), ("other", "Other")], required=True, index=True)
    template_index = fields.Integer(required=True)
    template_version = fields.Char(copy=False)
    valid = fields.Integer(default=1)
    template_size = fields.Integer(required=True)
    template = fields.Binary(required=True, copy=False, attachment=False)
    # Exact Security PUSH slot metadata is necessary for a lossless transfer.
    # Old caches remain valid for reading but must be refreshed before pushing.
    security_no = fields.Integer(readonly=True)
    security_index = fields.Integer(readonly=True)
    security_format = fields.Integer(readonly=True)
    security_duress = fields.Integer(readonly=True)
    security_type = fields.Integer(readonly=True)
    security_metadata_complete = fields.Boolean(readonly=True, default=False)
    updated_at = fields.Datetime(readonly=True)

    _zk_device_biometric_template_uniq = models.Constraint(
        "UNIQUE(device_id, pin, biometric_type, template_index)",
        "A biometric template slot must be unique per device and PIN.",
    )

    @api.model
    def upsert_from_adms(self, device, vals):
        values = {
            "biometric_type": vals["biometric_type"],
            "template_index": int(vals["template_index"]),
            "template_version": vals.get("template_version") or False,
            "valid": int(vals.get("valid", 1) if vals.get("valid") is not None else 1),
            "template_size": int(vals["template_size"]),
            "template": vals["template"],
            "updated_at": fields.Datetime.now(),
        }
        for field_name in (
            "security_no", "security_index", "security_format", "security_duress",
            "security_type", "security_metadata_complete",
        ):
            if field_name in vals:
                values[field_name] = vals[field_name]
        record = self.search([("device_id", "=", device.id), ("pin", "=", vals["pin"]), ("biometric_type", "=", values["biometric_type"]), ("template_index", "=", values["template_index"])], limit=1)
        if record:
            record.write(values)
        else:
            values.update({"device_id": device.id, "pin": vals["pin"]})
            record = self.create(values)
        return record


class ZkDeviceFingerprint(models.Model):
    _name = "zk.device.fingerprint"
    _description = "ZK Device Fingerprint Template (ADMS)"
    _order = "device_id, pin, finger_id"

    device_id = fields.Many2one("zk.device", required=True, ondelete="cascade", index=True)
    pin = fields.Char(required=True, index=True)
    finger_id = fields.Integer(required=True)
    valid = fields.Integer(default=1)
    template_size = fields.Integer(required=True)
    # The value is already base64 as supplied by the device. There is no public
    # view or ACL: only a deliberately unassigned internal service group has
    # model access, and protocol code operates through scoped sudo().
    template = fields.Binary(required=True, copy=False, attachment=False)
    updated_at = fields.Datetime(readonly=True)

    _zk_device_fingerprint_uniq = models.Constraint(
        "UNIQUE(device_id, pin, finger_id)",
        "A fingerprint slot must be unique per device and PIN.",
    )

    @api.model
    def upsert_from_adms(self, device, vals):
        values = {
            "valid": int(vals.get("valid", 1) if vals.get("valid") is not None else 1),
            "template_size": int(vals["size"]),
            "template": vals["tmp"],
            "updated_at": fields.Datetime.now(),
        }
        record = self.search([
            ("device_id", "=", device.id),
            ("pin", "=", vals["pin"]),
            ("finger_id", "=", int(vals["fid"])),
        ], limit=1)
        if record:
            record.write(values)
        else:
            values.update({
                "device_id": device.id,
                "pin": vals["pin"],
                "finger_id": int(vals["fid"]),
            })
            record = self.create(values)
        return record


class ZkDeviceCommand(models.Model):
    _name = "zk.device.command"
    _description = "ZK Device ADMS Command"
    _order = "id desc"

    device_id = fields.Many2one("zk.device", required=True, ondelete="cascade", index=True)
    command_id = fields.Integer(string="Command ID", required=True, readonly=True)
    # May contain a biometric template. Manager UI deliberately omits this raw
    # payload and shows only safe operation/status fields.
    command = fields.Text(
        required=True, copy=False,
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
        help="Private protocol command: can contain biometric data; never exposed in manager RPC.",
    )
    depends_on_id = fields.Many2one("zk.device.command", copy=False, ondelete="set null", readonly=True)
    # Exact transfer provenance is private, server-assigned metadata on the
    # normal-user PROFILE command only (never inside the device payload).
    transfer_requested_by = fields.Many2one(
        "res.users", copy=False, readonly=True, ondelete="set null",
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
    )
    transfer_source_user_id = fields.Many2one(
        "zk.device.user", copy=False, readonly=True, ondelete="set null",
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
    )
    transfer_employee_id = fields.Many2one(
        "hr.employee", copy=False, readonly=True, ondelete="set null",
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
    )
    transfer_pin = fields.Char(
        copy=False, readonly=True, index=True,
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
    )
    transfer_name = fields.Char(
        copy=False, readonly=True,
        groups="tam_hr_zk_attendance.group_biometric_protocol_internal",
    )
    operation = fields.Char(required=True, readonly=True, index=True, default="Legacy command")
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Sent"), ("done", "Done"), ("failed", "Failed"), ("cancelled", "Cancelled")],
        required=True,
        default="pending",
        index=True,
    )
    return_code = fields.Char(readonly=True)
    version_response = fields.Char(
        string="Safe Version Response", readonly=True, copy=False,
        help="Only validated firmware/PUSH release identifiers from approved diagnostic commands; never a raw device response."
    )
    sent_at = fields.Datetime(readonly=True)
    received_log_count = fields.Integer(string="Records Received", readonly=True,
                                        help="Raw attendance rows or accepted Security PUSH photo records, depending on the command.")
    skipped_log_count = fields.Integer(string="Duplicate / Invalid Logs", readonly=True)
    unmapped_log_count = fields.Integer(string="Unmapped Logs", readonly=True)
    last_payload_at = fields.Datetime(string="Last Payload", readonly=True)
    completed_at = fields.Datetime(readonly=True)
    waiting_too_long = fields.Boolean(string="Waiting Too Long", compute="_compute_waiting_too_long", search="_search_waiting_too_long", readonly=True)

    def _zk_apply_transfer_mapping(self, target_user=None):
        """Apply employee mapping only after device-confirmed enrollment.

        Do not create an optimistic target user on queue/ACK. The terminal must
        return the identity through a USER/user inventory response. Never alter
        a different existing employee's mapping or use a global PIN lookup.
        """
        self.ensure_one()
        if self.state != "done" or not (
            self.transfer_requested_by and self.transfer_source_user_id
            and self.transfer_employee_id and self.transfer_pin
        ):
            return False
        source = self.transfer_source_user_id.exists()
        employee = self.transfer_employee_id.exists()
        target = self.device_id
        if not source or not employee or not target or not target.is_approved:
            return False
        if source.employee_id != employee or source.device_id == target:
            return False
        requester = self.transfer_requested_by.exists()
        if not requester or not requester.active or (
            requester.id != SUPERUSER_ID
            and not requester.has_group("tam_hr_zk_attendance.group_biometric_manager")
        ):
            return False
        permitted = requester.company_ids.ids
        # Revalidate original requester's *current* rights at ACK/pull time.
        # The target can have a different owning company from the source;
        # neither a revoked source/target company nor revoked employee-company
        # access may silently attach an HR identity to that terminal.
        if (not source.device_id.company_id
                or source.device_id.company_id.id not in permitted
                or not target.company_id or target.company_id.id not in permitted
                or not employee.company_id or employee.company_id.id not in permitted):
            return False
        user = target_user or self.env["zk.device.user"].sudo().search([
            ("device_id", "=", target.id), ("pin", "=", self.transfer_pin),
        ], limit=1)
        if not user or user.device_id != target or user.pin != self.transfer_pin:
            return False
        # Do not rely on a stale inventory row from before the transfer was
        # queued; it might represent a person who previously used that PIN.
        if not user.updated_at or (self.create_date and user.updated_at < self.create_date):
            return False
        # PIN collision, renamed/privileged account, or conflicting employee:
        # never claim an unverified identity or replace an existing mapping.
        if not (self.transfer_name or "").strip() or (
            (user.name or "").strip() != (self.transfer_name or "").strip()
            or user.privilege != 0
        ):
            _logger.warning(
                "ZK transfer mapping not applied: destination identity differs "
                "(device_id=%s, PIN=%s, command_id=%s)",
                target.id, self.transfer_pin, self.command_id,
            )
            return False
        if user.employee_id:
            if user.employee_id != employee:
                _logger.warning(
                    "ZK transfer mapping not applied: destination already mapped "
                    "(device_id=%s, PIN=%s, command_id=%s)",
                    target.id, self.transfer_pin, self.command_id,
                )
            return user.employee_id == employee
        # An ADMS controller runs as a public user, whose company_ids would
        # reject any employee write. Re-check original operator visibility
        # rather than bypassing mapping guards via an unsafe context flag.
        try:
            user.with_user(requester).sudo().write({
                "employee_id": employee.id,
            })
        except (AccessError, ValidationError, UserError):
            _logger.warning(
                "ZK transfer mapping deferred: requesting manager no longer has "
                "permission for device_id=%s PIN=%s", target.id, self.transfer_pin,
            )
            return False
        _logger.info(
            "ZK transferred employee mapping verified: device_id=%s PIN=%s employee_id=%s",
            target.id, self.transfer_pin, employee.id,
        )
        return True

    def _compute_waiting_too_long(self):
        cutoff = fields.Datetime.now() - timedelta(minutes=15)
        for command in self:
            command.waiting_too_long = bool(command.state == "sent" and command.sent_at and command.sent_at < cutoff)

    def _search_waiting_too_long(self, operator, value):
        """Make the command-history stale filter usable in normal Odoo searches."""
        if operator not in ("=", "!="):
            return [("id", "=", 0)]
        expected = bool(value)
        if operator == "!=":
            expected = not expected
        cutoff = fields.Datetime.now() - timedelta(minutes=15)
        stale = [("state", "=", "sent"), ("sent_at", "!=", False), ("sent_at", "<", cutoff)]
        if expected:
            return stale
        return ["|", "|", ("state", "!=", "sent"), ("sent_at", "=", False), ("sent_at", ">=", cutoff)]

    def action_cancel(self):
        """Cancel only commands which have not yet left Odoo."""
        pending = self.filtered(lambda command: command.state == "pending")
        pending.write({"state": "cancelled", "completed_at": fields.Datetime.now()})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Command cancelled" if pending else "Command already delivered",
                "message": (
                    "%s queued command(s) will not be sent to the device." % len(pending)
                    if pending else "A sent command cannot be recalled; wait for its device response."
                ),
                "type": "success" if pending else "warning",
                "sticky": False,
            },
        }


    _zk_device_command_id_uniq = models.Constraint(
        "UNIQUE(device_id, command_id)", "Command ID must be unique per device."
    )
