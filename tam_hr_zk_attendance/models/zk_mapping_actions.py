# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError



def _notification(title, message, level="success"):
    return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {"title": title, "message": message, "type": level, "sticky": False},
    }


def _classic_adms_name_update_command(record):
    """Build Classic DATA USER with real TABs and validated field values.

    A previous literal ``\\t`` in this command created a second terminal user
    whose PIN contained all of the appended fields. Do not rely on a client
    escaping those characters: send actual ASCII tab delimiters.

    Unlike *transfer* (which creates a normal user on another terminal), a
    name-only update preserves this user's existing privilege and credentials.
    """
    from .classic_adms_transfer import PIN, _safe_text

    pin = record.pin or ""
    if not PIN.fullmatch(pin):
        raise UserError(_("Invalid Classic ADMS PIN; use the exact registered biometric ID."))

    name = _safe_text(record.name, _("device user name"))
    # Do not allow an untrusted name to look like a new key/value field or
    # like the escaped-tab payload that previously created a malformed PIN.
    if "=" in name or "\\t" in name:
        raise UserError(_("Device user name contains unsupported ADMS command characters."))

    def clean_field(value, label, max_length=128):
        value = str(value or "")
        if (len(value) > max_length or "=" in value or "\\t" in value
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
            raise UserError(_("Invalid %(field)s for Classic ADMS user update.", field=label))
        return value

    privilege = record.privilege
    if type(privilege) is not int or not 0 <= privilege <= 255:
        raise UserError(_("Invalid current device user privilege; update not queued."))

    fields = [
        "DATA USER PIN=%s" % pin,
        "Name=%s" % name,
        "Pri=%d" % privilege,
        "Passwd=%s" % clean_field(record.password, _("password")),
        "Card=%s" % clean_field(record.card, _("card")),
        "Grp=%s" % clean_field(record.group_id or "1", _("group")),
        "TZ=%s" % clean_field(record.timezone, _("timezone")),
    ]
    return "\t".join(fields)


class ZkDeviceUserMappingActions(models.Model):
    _inherit = "zk.device.user"

    def action_open_mapping_wizard(self):
        self.ensure_one()
        if not self.employee_id:
            return _notification(_("Employee required"), _("Choose a mapped employee before mapping historical punches."), "warning")
        return {
            "type": "ir.actions.act_window",
            "name": _("Map Historical Punches"),
            "res_model": "zk.attendance.mapping.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_device_user_id": self.id, "default_workflow": "map", "default_mapping_mode": "map_only", "default_mode": "map_only"},
        }

    def action_open_correction_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Fix Wrong Employee"),
            "res_model": "zk.attendance.mapping.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_device_user_id": self.id, "default_workflow": "correct", "default_correction_mode": "correct_raw", "default_mode": "correct_raw"},
        }

    def action_update_device_name(self):
        from .security_push_transfer import PIN_PATTERN, _validated_text

        if not (self.env.is_superuser() or self.env.user.has_group(
                "tam_hr_zk_attendance.group_biometric_manager")):
            raise UserError(_("Only Biometric Managers may update device users."))

        # Validate the *entire* selection before queueing any commands, so one
        # malformed PIN/name cannot leave a partial multi-user update batch.
        commands = []
        Command = self.env["zk.device.command"].sudo()
        for record in self:
            if not record.name:
                continue
            device = record.device_id
            if not device.is_approved:
                raise UserError(_("Approve the device before queuing user updates."))
            if device.company_id and device.company_id.id not in self.env.user.company_ids.ids:
                raise UserError(_("You must have access to the device's company."))
            if Command.search_count([
                ("device_id", "=", device.id),
                ("state", "in", ["pending", "sent"]),
            ]):
                raise UserError(_("Finish existing commands on this device before updating its user."))

            if (device.device_type or "").lower() == "acc":
                # Security PUSH uses a partial DATA UPDATE user operation:
                # never overwrite cards/passwords/admin/access settings.
                if not PIN_PATTERN.fullmatch(record.pin or ""):
                    raise UserError(_("Invalid Security PUSH user PIN."))
                name = _validated_text(record.name, _("device user name"))
                if "=" in name or "\\t" in name:
                    raise UserError(_("Device user name contains unsupported command characters."))
                command = "DATA UPDATE user Pin=%s\tName=%s" % (record.pin, name)
                operation = _("Update Security PUSH device user name")
            else:
                if (device.device_type or "").lower() not in ("att", ""):
                    raise UserError(_("Unsupported device protocol for name update."))
                command = _classic_adms_name_update_command(record)
                operation = _("Update device user")
            commands.append((device, command, operation))

        for device, command, operation in commands:
            device.queue_adms_command(command, operation)
        queued = len(commands)
        return _notification(
            _("Update queued") if queued else _("Name required"),
            _("The update is queued and will be sent the next time the biometric device connects to Odoo.") if queued else _("Enter a name before sending an update."),
            "success" if queued else "warning",
        )
