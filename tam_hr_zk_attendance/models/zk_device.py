# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ZkDevice(models.Model):
    _name = "zk.device"
    _description = "ZK Device"
    _order = "name asc"

    name = fields.Char(string="Device Serial (SN)", required=True, index=True)
    ip_address = fields.Char(string="IP Address", index=True)
    address_id = fields.Char(
        string="Device Location",
        help="Location of the physical device (office, factory floor, etc.).",
    )
    tz = fields.Selection(
        selection=lambda self: self.env["res.users"].fields_get(["tz"])["tz"]["selection"],
        string="Timezone",
        default="UTC",
        required=True,
        help="Timezone of the physical location of this device.",
    )
    allow_push = fields.Boolean(
        string="Allow Data Push",
        default=False,
        help="If unchecked, attendance payloads from this device are acknowledged but not stored.",
    )
    # Protocol diagnostics. These are populated automatically by the public
    # ADMS/Security PUSH endpoints and are intentionally read-only in the UI.
    device_type = fields.Char(string="Device Type", readonly=True)
    device_name = fields.Char(string="Reported Device Name", readonly=True)
    firmware_version = fields.Char(string="Firmware Version", readonly=True)
    push_version = fields.Char(
        string="Installed Push Version", readonly=True,
        help="Reported PushVersion field from Security PUSH registry, OPTIONS or a diagnostic reply."
    )
    adms_protocol_version = fields.Char(
        string="ADMS Handshake Version", readonly=True,
        help="The classic handshake pushver parameter (e.g. 2.4.1), not the installed PUSH application version."
    )
    last_metadata_at = fields.Datetime(string="Version Info Last Reported", readonly=True)
    metadata_source = fields.Char(string="Version Information Source", readonly=True)
    last_seen = fields.Datetime(string="Last Seen", readonly=True)
    last_user_sync_at = fields.Datetime(string="Users Last Refreshed", readonly=True)
    pending_command_count = fields.Integer(string="Pending Commands", compute="_compute_adms_command_status", readonly=True)
    device_user_count = fields.Integer(string="Device Users", compute="_compute_device_user_count", readonly=True)
    device_user_photo_count = fields.Integer(
        string="Cached Profile Pictures", compute="_compute_device_user_photo_count", readonly=True,
    )
    latest_command_state = fields.Selection(
        [("none", "No Commands"), ("pending", "Pending"), ("sent", "Sent"), ("done", "Done"), ("failed", "Failed"), ("cancelled", "Cancelled")],
        string="Latest Command Status",
        compute="_compute_adms_command_status",
        readonly=True,
    )
    connection_status = fields.Selection(
        [("online", "Online"), ("offline", "Offline")],
        string="ADMS Status",
        compute="_compute_connection_status",
        readonly=True,
    )
    last_registry_at = fields.Datetime(string="Last Registry", readonly=True)
    registry_code = fields.Char(string="Registry Code", readonly=True, copy=False)
    session_id = fields.Char(string="Push Session ID", readonly=True, copy=False)
    registry_payload = fields.Text(string="Registry Payload", readonly=True, copy=False)
    face_function_enabled = fields.Boolean(string="Face Function Enabled", readonly=True)
    finger_function_enabled = fields.Boolean(string="Fingerprint Function Enabled", readonly=True)
    max_finger_count = fields.Integer(string="Maximum Fingerprints", readonly=True)
    max_user_finger_count = fields.Integer(string="Maximum Fingerprints per User", readonly=True)
    max_multi_biodata_count = fields.Char(string="Multi-biometric Data Capacity", readonly=True)
    max_multi_biophoto_count = fields.Char(string="Multi-biometric Photo Capacity", readonly=True)
    multi_biodata_support = fields.Char(string="Multi-biometric Data Support Mask", readonly=True)
    multi_biophoto_support = fields.Char(string="Multi-biometric Photo Support Mask", readonly=True)
    multi_bio_version = fields.Char(string="Multi-biometric Algorithm Versions", readonly=True)
    sip_device_type = fields.Integer(string="SIP Device Type", readonly=True)
    zkfp_version = fields.Char(string="ZK Fingerprint Algorithm Version", readonly=True)
    adms_command_sequence = fields.Integer(string="ADMS Command Sequence", default=0, copy=False)

    @api.model
    def _adms_registration_company(self):
        """Return the deterministic company for an anonymous ADMS registration.

        A terminal talks to the public ADMS endpoint without an Odoo user or an
        active company context. Newly discovered devices are deliberately left
        unapproved and unable to send attendance; a manager assigns the final
        company and location before enabling the terminal.
        """
        return self.env["res.company"].sudo().search([], order="id", limit=1)

    def _compute_adms_command_status(self):
        Command = self.env["zk.device.command"].sudo()
        for device in self:
            pending_domain = [("device_id", "=", device.id), ("state", "in", ["pending", "sent"])]
            device.pending_command_count = Command.search_count(pending_domain)
            latest = Command.search([("device_id", "=", device.id)], order="id desc", limit=1)
            device.latest_command_state = latest.state if latest else "none"

    def _compute_device_user_count(self):
        DeviceUser = self.env["zk.device.user"].sudo()
        for device in self:
            device.device_user_count = DeviceUser.search_count([("device_id", "=", device.id)])


    def _compute_device_user_photo_count(self):
        users = self.env["zk.device.user"].sudo()
        for device in self:
            device.device_user_photo_count = users.search_count([
                ("device_id", "=", device.id), ("image_1920", "!=", False),
            ])

    def action_pull_profile_pictures(self):
        """Request available photographs with the device-native PUSH protocol.

        Security PUSH can query USERPIC table; Classic/legacy can only refresh
        upload options and request pending uploads (not historical photos).
        Receipt is monitored separately from command acknowledgment.
        """
        self.ensure_one()
        if not (self.env.is_superuser() or self.env.user.has_group(
            "tam_hr_zk_attendance.group_biometric_manager"
        )):
            raise UserError(_("Only Biometric Managers may request profile pictures."))
        if not self.is_approved:
            raise UserError(_("Approve this device before requesting profile pictures."))
        protocol = (self.device_type or "").strip().lower()
        if protocol not in ("acc", "att", ""):
            raise UserError(_("Unrecognized device protocol; inspect registration before requesting pictures."))
        if not self.company_id or self.company_id.id not in self.env.user.company_ids.ids:
            raise UserError(_("You do not have access to this device company."))
        if self.env["zk.device.command"].sudo().search_count([
            ("device_id", "=", self.id), ("state", "in", ["pending", "sent"]),
        ]):
            raise UserError(_("Finish the device's active commands before requesting pictures."))
        if protocol == "acc":
            command = self.queue_adms_command(
                "DATA QUERY tablename=userpic,fielddesc=*,filter=*",
                _("Pull profile pictures (Security PUSH)"),
            )
            message = _(
                "Security PUSH photo query %(id)s queued. Actual stored photos are the "
                "result; the terminal may return -1 despite uploading images.",
                id=command.command_id,
            )
        else:
            # Classic PUSH does not document a historical USERPIC QUERY. CHECK
            # refreshes TransFlag, and LOG requests available pending uploads;
            # neither can force an old portrait out of unsupported firmware.
            check = self.queue_adms_command(
                "CHECK", _("Classic photo sync: refresh upload options"),
            )
            command = self.queue_adms_command(
                "LOG", _("Classic photo sync: request pending uploads"),
                depends_on=check,
            )
            message = _(
                "Classic commands %(check)s and %(log)s queued. These request "
                "pending uploads only, not a guaranteed historical portrait pull. "
                "If no USERPIC arrives, the firmware may require a new photo update "
                "or an export outside ADMS.",
                check=check.command_id, log=command.command_id,
            )
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Profile picture synchronization requested"),
                "message": message,
                "type": "info", "sticky": False,
            },
        }

    def action_open_device_commands(self):
        self.ensure_one()
        action = self.env.ref("tam_hr_zk_attendance.zk_device_command_action").read()[0]
        action["domain"] = [("device_id", "=", self.id)]
        action["context"] = {"default_device_id": self.id}
        return action

    def action_open_device_users(self):
        self.ensure_one()
        action = self.env.ref("tam_hr_zk_attendance.zk_device_user_action").read()[0]
        action["domain"] = [("device_id", "=", self.id)]
        action["context"] = {"default_device_id": self.id}
        return action


    @api.model
    def _online_cutoff(self):
        return fields.Datetime.now() - timedelta(minutes=2)


    def _compute_connection_status(self):
        """A terminal is online when it contacted ADMS during the last 2 minutes."""
        cutoff = self._online_cutoff()
        for device in self:
            device.connection_status = "online" if device.last_seen and device.last_seen >= cutoff else "offline"

    def action_open_attendance_pull_wizard(self):
        self.ensure_one()
        if (self.device_type or "").lower() == "acc":
            raise UserError(_(
                "Historical attendance pulls are not supported by Security PUSH "
                "devices. Attendance is received when the terminal pushes RTLOG "
                "events to Odoo. Reconnect the device and check its ADMS setup."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pull Attendance"),
            "res_model": "zk.attendance.pull.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_device_id": self.id},
        }

    def record_attendance_payload(self, created, skipped, unmapped):
        """Expose received raw-log progress without retaining sensitive payloads."""
        self.ensure_one()
        Command = self.env["zk.device.command"].sudo()
        command = Command.search([
            ("device_id", "=", self.id),
            ("state", "in", ["sent", "done"]),
            ("command", "ilike", "DATA QUERY ATTLOG"),
        ], order="id desc", limit=1)
        if command:
            command.write({
                "received_log_count": command.received_log_count + created,
                "skipped_log_count": command.skipped_log_count + skipped,
                "unmapped_log_count": command.unmapped_log_count + unmapped,
                "last_payload_at": fields.Datetime.now(),
            })
        return command
    def action_request_device_info(self):
        """Request only read-only Classic ADMS firmware diagnostics.

        Acknowledgement alone does not prove the device sent a version value;
        the new metadata timestamp changes only after an actual identifier.
        """
        self.ensure_one()
        if not (self.env.is_superuser() or self.env.user.has_group(
            "tam_hr_zk_attendance.group_biometric_manager"
        )):
            raise UserError(_("Only Biometric Managers may request device information."))
        if not self.is_approved or (self.device_type or "").lower() != "att":
            raise UserError(_("Version requests are enabled for approved Classic ADMS terminals only."))
        if self.env["zk.device.command"].sudo().search_count([
            ("device_id", "=", self.id), ("state", "in", ["pending", "sent"])
        ]):
            raise UserError(_("Finish pending commands before requesting device information."))
        for command, description in (
            ("INFO", _("Request device information")),
            ("GET OPTION FROM FWVersion", _("Request firmware version")),
            ("GET OPTION FROM PushVersion", _("Request installed PUSH software version")),
        ):
            self.queue_adms_command(command, description)
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Device information requested"),
                       "message": _("Three read-only requests queued. Look for a Safe Version Response; Return 0 alone is not a version."),
                       "type": "info", "sticky": False},
        }

    def queue_adms_command(self, command, operation=None, depends_on=None):
        """Allocate command IDs under a device row lock and respect DB history.

        A concurrent web request or a stale sequence must not reuse IDs.
        The caller's transaction manages commit/rollback normally.
        """
        self.ensure_one()
        if not self.is_approved and command.startswith((
            "DATA USER", "DATA FP", "DATA QUERY USERINFO",
            "DATA QUERY tablename=", "DATA UPDATE user ", "DATA UPDATE biodata ",
            "DATA UPDATE userpic ", "DATA UPDATE FACE ",
            "DATA UPDATE USERPIC ", "DATA QUERY BIODATA ",
        )):
            raise UserError(_("Approve this device before queuing biometric commands."))
        self.env.cr.execute("SELECT id FROM zk_device WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["adms_command_sequence"])
        self.env.cr.execute(
            "SELECT COALESCE(MAX(command_id), 0) FROM zk_device_command WHERE device_id = %s",
            [self.id],
        )
        highest_id = self.env.cr.fetchone()[0]
        next_id = max(self.adms_command_sequence or 0, highest_id) + 1
        self.write({"adms_command_sequence": next_id})
        return self.env["zk.device.command"].sudo().create({
            "device_id": self.id,
            "command_id": next_id,
            "command": command,
            "operation": operation or command.split(" ", 2)[0],
            "depends_on_id": depends_on.id if depends_on else False,
        })

    def next_adms_command(self):
        """Only deliver a biometric template after its predecessor succeeds."""
        self.ensure_one()
        Command = self.env["zk.device.command"].sudo()
        while True:
            command = Command.search([
                ("device_id", "=", self.id), ("state", "=", "pending"),
            ], order="id asc", limit=1)
            if not command:
                return command
            dependency = command.depends_on_id
            if dependency and dependency.state in ("failed", "cancelled"):
                command.write({"state": "cancelled", "completed_at": fields.Datetime.now()})
                continue
            if dependency and dependency.state != "done":
                return Command.browse()
            # A Security PUSH user-query ACK only proves receipt of the
            # query/row count. Before sending biometric/photo bytes, insist on
            # an actual fresh target user row with this exact PIN, name and
            # normal role. Out-of-order querydata packets cannot bypass this.
            if (dependency and dependency.operation == "Complete transfer: verify target user"
                    and dependency.transfer_pin and dependency.transfer_name):
                verified = self.env["zk.device.user"].sudo().search([
                    ("device_id", "=", self.id),
                    ("pin", "=", dependency.transfer_pin),
                ], limit=1)
                if not verified or not verified.updated_at or not dependency.sent_at or (
                    verified.updated_at < dependency.sent_at
                ):
                    return Command.browse()
                if (verified.privilege != 0 or (verified.name or "").strip()
                        != (dependency.transfer_name or "").strip()):
                    command.write({"state": "cancelled", "completed_at": fields.Datetime.now()})
                    continue
            command.write({"state": "sent", "sent_at": fields.Datetime.now()})
            return command

    def acknowledge_adms_command(self, command_id, return_code):
        self.ensure_one()
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.id),
            ("command_id", "=", int(command_id)),
            ("state", "in", ["sent", "done"]),
        ], limit=1)
        if command and (command.state == "sent" or command.command.startswith("DATA QUERY tablename=")):
            code = str(return_code if return_code is not None else "")
            command.write({
                "return_code": code,
                # Security PUSH query ACK 'Return' is a row count (0, 1, 2, ...),
                # whereas classic attendance ADMS uses the existing 0/1 convention.
                "state": "done" if (
                    (command.command.startswith("DATA QUERY tablename=") and code.isdigit())
                    or (command.command.startswith("DATA UPDATE ") and code == "0")
                    or (not command.command.startswith(("DATA QUERY tablename=", "DATA UPDATE ")) and code in {"0", "1"})
                ) else "failed",
                "completed_at": fields.Datetime.now(),
            })
            if command.state == "done" and command.transfer_employee_id:
                command._zk_apply_transfer_mapping()
        return command

    def complete_query_from_payload(self, command_prefix, received_user_pins=None):
        """Complete a sent query only after receiving its requested data.

        For Classic USERINFO PIN=<pin>, another user's USER record or any FP
        packet must NOT complete the command. Bulk USERINFO queries require at
        least one USER row. ATTLOG keeps its previous completion behavior.
        """
        self.ensure_one()
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.id),
            ("state", "=", "sent"),
            ("command", "ilike", command_prefix + "%"),
        ], order="id asc", limit=1)
        if command and command_prefix == "DATA QUERY USERINFO" and received_user_pins is not None:
            if not received_user_pins:
                return False
            import re
            match = re.search(r"(?:^|\s)PIN=([^\s]+)", command.command, re.IGNORECASE)
            if match and match.group(1) not in received_user_pins:
                return False
        if command:
            now = fields.Datetime.now()
            command.write({
                "state": "done",
                "return_code": "payload_received",
                "last_payload_at": now,
                "completed_at": now,
            })
        return command


    def _get_adms_timezone_offset(self):
        """Return ZKTeco ADMS ``TimeZone`` value from the selected timezone."""
        self.ensure_one()
        tz_name = self.tz or "UTC"
        try:
            tz = pytz.timezone(tz_name)
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            offset = now_utc.astimezone(tz).utcoffset()
            if not offset:
                return "0"
            hours = offset.total_seconds() / 3600.0
            if hours.is_integer():
                return str(int(hours))
            return ("%.2f" % hours).rstrip("0").rstrip(".")
        except Exception:
            return "0"
