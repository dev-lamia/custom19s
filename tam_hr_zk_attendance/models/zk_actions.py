# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError
import re


def _notification(title, message, level="success"):
    return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {
            "title": title,
            "message": message,
            "type": level,
            "sticky": False,
        },
    }


class ZkDeviceUserActions(models.Model):
    _inherit = "zk.device.user"

    target_device_id = fields.Many2one("zk.device", string="Push To Device", ondelete="restrict", check_company=True)

    def action_pull_from_device(self):
        for record in self:
            if (record.device_id.device_type or "").lower() == "acc":
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", record.pin or ""):
                    raise UserError(_("Invalid device user PIN for Security PUSH query."))
                command = "DATA QUERY tablename=user,fielddesc=*,filter=Pin=%s" % record.pin
            else:
                command = "DATA QUERY USERINFO PIN=%s" % record.pin
            record.device_id.queue_adms_command(command, "Refresh device user")
        return _notification(
            _("Refresh queued"),
            _("The refresh is queued and will be sent the next time the biometric device connects to Odoo. Check Command History for progress.", pin=self.pin),
        )


    def action_open_batch_transfer_wizard(self):
        """List-view Action menu: transfer only explicitly selected source users."""
        if not (self.env.is_superuser() or self.env.user.has_group(
            "tam_hr_zk_attendance.group_biometric_manager"
        )):
            raise UserError(_("Only Biometric Managers may transfer users."))
        if not self or len(self) > 25:
            raise UserError(_("Select between 1 and 25 device users for one transfer batch."))
        if len(self.mapped("device_id")) != 1:
            raise UserError(_("Select users from one source device only."))
        if len(set(self.mapped("pin"))) != len(self):
            raise UserError(_("The selected users include duplicate device PINs."))
        source = self[0].device_id
        # The wizard is protocol aware. Classic/legacy ADMS sources are valid;
        # the target compatibility and supported operations are checked on submit.
        if (source.device_type or "").strip().lower() not in ("acc", "att", ""):
            raise UserError(_(
                "Source %(serial)s reports unsupported protocol '%(protocol)s'. "
                "Inspect its registration before sending any device commands.",
                serial=source.serial_number or source.display_name,
                protocol=source.device_type,
            ))
        if not source.is_approved:
            raise UserError(_(
                "Selected source %(serial)s is not approved in Odoo. "
                "Check this source device's approval before transferring. "
                "Nothing was queued.",
                serial=source.serial_number or source.display_name,
            ))
        if not source.company_id or source.company_id.id not in self.env.user.company_ids.ids:
            raise UserError(_("You do not have access to the source company."))
        wizard = self.env["zk.device.user.batch.transfer.wizard"].create({
            "source_device_id": source.id,
            "device_user_ids": [(6, 0, self.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer Selected Device Users"),
            "res_model": "zk.device.user.batch.transfer.wizard",
            "res_id": wizard.id, "view_mode": "form", "target": "new",
            "context": {"form_view_initial_mode": "edit"},
        }

    def action_open_transfer_wizard(self):
        self.ensure_one()
        # Pre-create a real transient record. Opening an unsaved form with
        # create/edit disabled produced action_transfer() on an empty recordset
        # (Expected singleton: zk.device.user.transfer.wizard()).
        wizard = self.env["zk.device.user.transfer.wizard"].create({
            "device_user_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer Device User"),
            "res_model": "zk.device.user.transfer.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            # The record already exists; open it directly in editable mode so
            # the manager can choose the target and confirm the transfer.
            "context": {"form_view_initial_mode": "edit"},
        }

    def _queue_transfer_to_device(self, target_device=None, transfer_mode="full", operations=None,
                                  authorization_timezone_id=0, authorization_door_id=0, authorization_group_id=0,
                                  preflight_only=False, allow_batch_pending=False,
                                  batch_previous_command=None):
        Fingerprint = self.env["zk.device.fingerprint"].sudo()
        queued = 0
        # Cross-company selections are allowed only for a Biometric Manager
        # assigned to BOTH terminal companies. Extend active-company context
        # to their assigned companies; never sudo the user/device selector.
        allowed_companies = self.env.user.company_ids.ids
        for record in self.with_context(allowed_company_ids=allowed_companies):
            if not (self.env.is_superuser() or self.env.user.has_group(
                "tam_hr_zk_attendance.group_biometric_manager"
            )):
                raise UserError(_("Only Biometric Managers may transfer device users."))
            target = target_device or record.target_device_id
            if not target:
                raise UserError(_("Select a target biometric device before transferring this user."))
            target = target.with_context(allowed_company_ids=allowed_companies)
            # Re-check both companies on submission, not just in the dropdown.
            # A forged target ID cannot authorize a cross-company transfer.
            if (not record.device_id.company_id
                    or record.device_id.company_id.id not in allowed_companies
                    or not target.company_id
                    or target.company_id.id not in allowed_companies):
                raise UserError(_("You must have access to both source and destination device companies."))
            if not target.is_approved or not record.device_id.is_approved:
                raise UserError(_("Approve both biometric devices before transferring a user or biometric templates."))
            if record.employee_id:
                # Biometric Managers may not read the private hr.employee model.
                # Check source employee visibility using the public HR directory.
                public_employee = self.env["hr.employee.public"].with_context(
                    allowed_company_ids=allowed_companies,
                ).search([("id", "=", record.employee_id.id)], limit=1)
                if not public_employee or public_employee.company_id.id not in allowed_companies:
                    raise UserError(_("You must have access to the mapped employee company."))
            if (target.device_type or "").lower() == "acc" or (record.device_id.device_type or "").lower() == "acc":
                if (target.device_type or "").lower() != "acc" or (record.device_id.device_type or "").lower() != "acc":
                    raise UserError(_("Transfers between classic ADMS and Security PUSH devices are not supported."))
                queued += record._queue_security_push_transfer(
                    target, transfer_mode=transfer_mode, operations=operations,
                    authorization_timezone_id=authorization_timezone_id,
                    authorization_door_id=authorization_door_id,
                    authorization_group_id=authorization_group_id,
                    preflight_only=preflight_only, allow_batch_pending=allow_batch_pending,
                    batch_previous_command=batch_previous_command,
                )
                continue
            queued += record._queue_classic_adms_transfer(
                target, transfer_mode=transfer_mode, operations=operations,
                preflight_only=preflight_only,
                allow_batch_pending=allow_batch_pending,
                batch_previous_command=batch_previous_command,
            )
        return _notification(
            _("Transfer queued"),
            _("%(count)s update(s) are waiting for the target biometric device.", count=queued),
        )


class ZkDeviceActions(models.Model):
    _inherit = "zk.device"

    def action_restart_device(self):
        """Queue a terminal restart; ADMS devices execute it on their next poll."""
        Command = self.env["zk.device.command"].sudo()
        for device in self:
            if (device.device_type or "").lower() == "acc":
                raise UserError(_("Remote restart is not yet verified for Security PUSH devices."))
            if not device.is_approved:
                raise UserError(_("Approve this biometric device before queuing a restart."))
            active_command = Command.search([
                ("device_id", "=", device.id),
                ("state", "in", ("pending", "sent")),
            ], limit=1)
            if active_command:
                raise UserError(_(
                    "Finish or cancel the device's queued commands before restarting it."
                ))
            device.queue_adms_command("REBOOT", _("Restart device"))
        return _notification(
            _("Device restart queued"),
            _("The terminal will restart when it next polls Odoo. This does not restart Odoo.sh."),
            "warning",
        )

    def action_pull_attendance(self):
        security_push_devices = self.filtered(
            lambda device: (device.device_type or "").lower() == "acc"
        )
        if security_push_devices:
            raise UserError(_(
                "Historical attendance pulls are not supported by Security PUSH "
                "devices (%(devices)s). These terminals push RTLOG attendance "
                "events to Odoo; reconnect the device and verify its ADMS "
                "connection instead.",
                devices=", ".join(security_push_devices.mapped("name")),
            ))
        for device in self:
            device.queue_adms_command("DATA QUERY ATTLOG", "Pull all attendance logs")
        return _notification(
            _("Attendance pull queued"),
            _("The request is queued and will be sent the next time the biometric device connects to Odoo. Check Command History for progress."),
        )

    def action_pull_users(self):
        for device in self:
            if (device.device_type or "").lower() == "acc":
                # Each Security PUSH table is a separate query and may return
                # multiple packages. Both devices advertise biometric types 1/9.
                device.queue_adms_command(
                    "DATA QUERY tablename=user,fielddesc=*,filter=*",
                    "Pull users and biometric templates",
                )
                for bio_type, label in ((1, "Fingerprint"), (9, "Visible-face")):
                    device.queue_adms_command(
                        "DATA QUERY tablename=biodata,fielddesc=*,filter=Type=%s" % bio_type,
                        "Pull %s templates (Security PUSH)" % label,
                    )
            else:
                device.queue_adms_command("DATA QUERY USERINFO", "Pull users and biometric templates")
                device.queue_adms_command(
                    "DATA QUERY BIODATA Type=9", "Pull Classic visible-light face templates",
                )
        return _notification(
            _("User and template pull queued"),
            _("The request is queued and will be sent the next time the biometric device connects to Odoo. Check Command History for progress."),
        )

    def action_pull_classic_faces(self):
        """Read device-resident Type 9 face enrollment without altering users.

        Firmware may respond via /iclock/cdata?table=BIODATA or OPERLOG.
        Do not queue blindly on ACC devices, and never clear enrollment data.
        """
        Command = self.env["zk.device.command"].sudo()
        for device in self:
            if not (self.env.is_superuser() or self.env.user.has_group(
                    "tam_hr_zk_attendance.group_biometric_manager")):
                raise UserError(_("Only Biometric Managers may request face templates."))
            if not device.is_approved or (device.device_type or "").lower() not in ("att", ""):
                raise UserError(_("Select an approved Classic ATT terminal for the face query."))
            if device.company_id.id not in self.env.user.company_ids.ids:
                raise UserError(_("Access to the terminal company is required."))
            if Command.search_count([
                ("device_id", "=", device.id),
                ("state", "in", ("pending", "sent")),
            ]):
                raise UserError(_("Finish the device's existing commands before querying faces."))
            device.queue_adms_command(
                "DATA QUERY BIODATA Type=9",
                "Pull Classic ATT visible-light face templates",
            )
        return _notification(
            _("Classic face query queued"),
            _("The device will return native Type 9 templates if this firmware supports the command. Inspect Command History and cached face counts."),
        )

    def action_sync_timezone(self):
        for device in self:
            if (device.device_type or "").lower() == "acc":
                raise UserError(_("Timezone synchronization is not yet verified for Security PUSH devices."))
            device.queue_adms_command("SET OPTION TimeZone=%s" % device._get_adms_timezone_offset(), "Synchronize timezone")
        return _notification(
            _("Timezone synchronization queued"),
            _("The timezone update is queued and will be sent the next time the biometric device connects to Odoo. Check Command History for progress."),
        )
