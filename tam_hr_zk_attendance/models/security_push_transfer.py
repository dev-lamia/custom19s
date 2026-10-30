# -*- coding: utf-8 -*-
"""Validated Security PUSH transfers for access-control devices.

Transfer workflow deliberately defaults to one profile. Biometric transfer is
an explicit second step after the target user has been verified by a fresh pull.
Never expose biometric command bodies to non-protocol users.
"""
import base64
import binascii
import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


PIN_PATTERN = re.compile(r"[0-9]{1,12}\Z")


def _metadata(payload):
    values = {}
    for part in re.split(r"[,\r\n]", payload or ""):
        if "=" in part:
            key, value = part.split("=", 1)
            values[key.strip().lstrip("~").lower()] = value.strip()
    return values


def _validated_text(text, label, max_length=80):
    text = (text or "").strip()
    if not text or len(text) > max_length or any(ord(c) < 32 for c in text):
        raise UserError(_("Invalid %(label)s for Security PUSH transfer.", label=label))
    return text


def _format_profile(user, destination_group=1):
    """Security PUSH normal-role enrollment; source admin status is never copied."""
    pin = user.pin or ""
    if not PIN_PATTERN.fullmatch(pin):
        raise UserError(_("Only 1–12 digit user PINs can be transferred to this terminal."))
    name = _validated_text(user.name, _("employee name"))
    if type(destination_group) is not int or not 1 <= destination_group <= 99:
        raise UserError(_("Choose a valid destination access group (1–99)."))
    # Do not move access cards, keypad passwords or authorization settings in a
    # biometric enrollment transfer. These are separate security decisions.
    return "DATA UPDATE user " + "\t".join([
        "CardNo=", "Pin=%s" % pin, "Password=", "Group=%s" % destination_group,
        # StartTime=0 / EndTime=0 were previously sent without knowing
        # how this terminal interpreted the optional validity interval.
        # Leave them unspecified; authorization is a separate deliberate step.
        "Name=%s" % name, "Privilege=0",
    ])


def _format_user_authorization(pin, timezone_id, door_id):
    """Explicit, destination-approved access policy; never infer from Group 1.

    TimezoneId 1 may mean 24h access on some firmware, hence no implicit
    default. This operation must follow an authorized selection in the wizard.
    """
    if not PIN_PATTERN.fullmatch(pin or ""):
        raise UserError(_("Invalid user PIN for access authorization."))
    if type(timezone_id) is not int or not 1 <= timezone_id <= 50:
        raise UserError(_("Select a valid destination time-period ID (1–50)."))
    if type(door_id) is not int or not 1 <= door_id <= 16:
        raise UserError(_("Select a valid destination door ID (1–16)."))
    return "DATA UPDATE userauthorize " + "\t".join([
        "Pin=%s" % pin,
        "AuthorizeTimezoneId=%s" % timezone_id,
        "AuthorizeDoorId=%s" % door_id,
    ])



def _format_profile_picture(target, pin, photo):
    """Prepare Security PUSH's DATA UPDATE userpic without exposing the JPEG.

    This is a *destination write* for a separately verified existing user, not
    an enrollment, face template, or access-authorization operation. The caller
    must validate device/company/employee identity before invoking it.
    """
    if not PIN_PATTERN.fullmatch(pin or ""):
        raise UserError(_("Invalid PIN for photo transfer."))
    if not photo:
        raise UserError(_("The source device has no cached profile picture. Pull its photos first."))
    if isinstance(photo, bytes):
        encoded_source = photo
    elif isinstance(photo, str):
        encoded_source = photo.encode("ascii")
    else:
        raise UserError(_("Unrecognized cached profile-picture data."))
    if len(encoded_source) > 3 * 1024 * 1024:
        raise UserError(_("The cached profile picture exceeds the allowed size."))
    try:
        raw = base64.b64decode(encoded_source, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise UserError(_("The source profile picture is not valid base64.")) from exc
    if not raw or len(raw) > 2 * 1024 * 1024 or not raw.startswith(b"\xff\xd8\xff"):
        raise UserError(_("Only JPEG profile pictures of at most 2 MiB can be transferred."))
    try:
        with Image.open(io.BytesIO(raw)) as picture:
            if picture.format != "JPEG" or picture.width * picture.height > 8_000_000:
                raise UserError(_("Unsupported source profile-picture dimensions."))
            picture.load()
            normalized = ImageOps.exif_transpose(picture).convert("RGB")
            stream = io.BytesIO()
            # Re-encode with no EXIF/metadata even if the image was later
            # replaced manually in Odoo instead of imported from the device.
            normalized.save(stream, format="JPEG", quality=85, optimize=True)
            sanitized = stream.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise UserError(_("The source profile picture is not a valid JPEG.")) from exc
    if not sanitized or len(sanitized) > 2 * 1024 * 1024:
        raise UserError(_("The sanitized profile picture exceeds the allowed size."))
    encoded = base64.b64encode(sanitized).decode("ascii")
    payload = "DATA UPDATE userpic " + "\t".join([
        "pin=%s" % pin, "size=%d" % len(encoded), "format=0",
        "content=%s" % encoded,
    ])
    metadata = _metadata(target.registry_payload)
    try:
        packet_limit = int(metadata.get("maxpackagesize") or 0)
    except (ValueError, TypeError) as exc:
        raise UserError(_("Invalid target Security PUSH maximum package size.")) from exc
    if not packet_limit or len(payload.encode("ascii")) > min(packet_limit, 2_048_000):
        raise UserError(_(
            "Profile picture exceeds the destination's advertised package limit, "
            "or the destination has not supplied its package limit."
        ))
    return payload


def _registry_algorithm(device, biometric_type):
    info = _metadata(device.registry_payload)
    support = info.get("multibiodatasupport", "").split(":")
    versions = info.get("multibioversion", "").split(":")
    if len(support) <= biometric_type or support[biometric_type] != "1":
        raise UserError(_("Device %(device)s does not advertise support for biometric type %(type)s.", device=device.display_name, type=biometric_type))
    if len(versions) <= biometric_type or not versions[biometric_type].strip():
        raise UserError(_("Device %(device)s has no reported algorithm version for biometric type %(type)s.", device=device.display_name, type=biometric_type))
    return versions[biometric_type].strip(), int(info.get("maxpackagesize", "0") or "0")


def _format_template(source, target, template):
    """Require exact source metadata and identical advertised algorithms."""
    if not template.security_metadata_complete or template.security_type not in (1, 9):
        raise UserError(_("Biometric metadata is incomplete. Pull users and templates again from the source device after this upgrade."))
    kind = {1: "fingerprint", 9: "face"}[template.security_type]
    if template.biometric_type != kind:
        raise UserError(_("Inconsistent cached biometric template type; transfer stopped."))
    source_ver, _source_limit = _registry_algorithm(source, template.security_type)
    target_ver, target_limit = _registry_algorithm(target, template.security_type)
    cached_ver = (template.template_version or "").split(";", 1)[0]
    if source_ver != target_ver or cached_ver != source_ver:
        raise UserError(_("Biometric algorithm versions differ or do not match the cached template. Transfer is blocked."))
    if template.security_format != 0 or template.security_duress != 0:
        raise UserError(_("Only non-duress native ZK biometric templates have been enabled for the first transfer."))
    if template.valid != 1:
        raise UserError(_("Invalid biometric templates cannot be transferred."))
    encoded = template.template
    if isinstance(encoded, bytes):
        try:
            encoded = encoded.decode("ascii")
        except UnicodeDecodeError as exc:
            raise UserError(_("Invalid cached biometric encoding.")) from exc
    try:
        decoded = base64.b64decode(encoded or "", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise UserError(_("Invalid cached biometric encoding.")) from exc
    if not decoded or len(decoded) != template.template_size:
        raise UserError(_("Biometric payload length does not match the cached template."))
    version = cached_ver.split(".")
    if len(version) != 2 or not all(item.isdigit() for item in version):
        raise UserError(_("Invalid cached biometric algorithm version."))
    no = template.security_no
    index = template.security_index
    if no < 0 or no > 99 or index < 0 or index > 655:
        raise UserError(_("Invalid biometric slot metadata."))
    data = "DATA UPDATE biodata " + "\t".join([
        "Pin=%s" % template.pin, "No=%s" % no, "Index=%s" % index,
        "Valid=1", "Duress=0", "Type=%s" % template.security_type,
        "MajorVer=%s" % version[0], "MinorVer=%s" % version[1],
        "Format=0", "Tmp=%s" % encoded,
    ])
    if not target_limit or len(data.encode("utf-8")) > min(target_limit, 2048000):
        raise UserError(_("Biometric template exceeds the target terminal's advertised package size."))
    return data


class ZkSecurityPushInventory(models.Model):
    _inherit = "zk.device"

    def _security_push_user_inventory_status(self):
        """Read-only proof of a recent user inventory, including zero users.

        Security PUSH terminals may respond to an empty DATA QUERY user with
        DEVICECMD Return=0 and no /iclock/querydata payload. Consequently the
        cached last_user_sync_at is not necessarily populated. This must not
        prevent enrolling the *first* user on a freshly queried terminal.

        Only the latest full-user query is considered; never confuse a generic
        successful command (or the old USERINFO query) with an inventory check.
        """
        self.ensure_one()
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        if self.last_user_sync_at and self.last_user_sync_at >= cutoff:
            return "records"
        if (self.device_type or "").lower() != "acc":
            return False

        latest = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.id),
            ("command", "=", "DATA QUERY tablename=user,fielddesc=*,filter=*"),
        ], order="command_id desc, id desc", limit=1)
        if not latest or latest.state != "done" or not latest.completed_at:
            return False
        if latest.completed_at < cutoff:
            return False
        # The terminal explicitly acknowledged a successful empty query.
        # Querydata is not required for zero rows, and must not be fabricated.
        if str(latest.return_code or "").strip() == "0":
            return "empty"
        if latest.last_payload_at:
            return "records"
        return False


class ZkSecurityPushTransfer(models.Model):
    _inherit = "zk.device.user"

    def _queue_security_push_transfer(self, target, transfer_mode="profile_only",
                                      authorization_timezone_id=0, authorization_door_id=0,
                                      authorization_group_id=0, preflight_only=False, allow_batch_pending=False,
                                      batch_previous_command=None, operations=None):
        """Queue a validated command chain; never send template data before profile verification.

        ``full`` is the default *wizard* experience. The historical named
        stages remain supported for code/API callers, but are no longer needed
        for normal transfers. Preflight all binary payloads and identity checks
        before queuing any commands. The transaction rolls back atomically on
        validation/SQL errors.
        """
        self.ensure_one()
        if operations is not None:
            return self._queue_security_push_operations(
                target, operations, authorization_timezone_id, authorization_door_id,
                authorization_group_id, preflight_only, allow_batch_pending,
                batch_previous_command,
            )
        if transfer_mode not in (
            "full", "profile_only", "templates_only", "authorize_only", "face_only", "photo_only"
        ):
            raise UserError(_("Select the complete transfer or a supported repair operation."))
        if preflight_only and transfer_mode not in ("full", "photo_only", "face_only"):
            raise UserError(_("Batch preflight supports full, face-only and photo-only Security PUSH transfers."))
        source = self.device_id
        if (source.device_type or "").lower() != "acc" or (target.device_type or "").lower() != "acc":
            raise UserError(_("Both terminals must use Security PUSH."))
        if not source.is_approved or not target.is_approved or source.id == target.id:
            raise UserError(_("Select a different approved Security PUSH terminal."))
        permitted = self.env.user.company_ids.ids
        if (not source.company_id or source.company_id.id not in permitted
                or not target.company_id or target.company_id.id not in permitted):
            raise UserError(_("You must have access to both source and destination device companies."))
        if not (self.env.is_superuser() or self.env.user.has_group("tam_hr_zk_attendance.group_biometric_manager")):
            raise UserError(_("Only Biometric Managers may transfer device users."))
        if not target._security_push_user_inventory_status():
            raise UserError(_(
                "Refresh the target's user inventory first. A successful Security PUSH user "
                "query returning zero users is valid for an empty target."
            ))
        if not allow_batch_pending and self.env["zk.device.command"].sudo().search_count([
            ("device_id", "=", target.id), ("state", "in", ("pending", "sent"))
        ]):
            raise UserError(_("Finish or cancel the target terminal's existing commands before transferring."))

        conflict = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", target.id), ("pin", "=", self.pin)
        ], limit=1)
        if conflict:
            # A normal user's valid fingerprint/face access must not be
            # overwritten by another person with the same numerical PIN.
            if conflict.privilege != 0:
                raise UserError(_("The destination PIN is not a normal user; inspect it manually."))
            if _validated_text(conflict.name, _("target user name")) != _validated_text(self.name, _("source user name")):
                raise UserError(_("The destination PIN has a different name. Review identity before transferring."))
            if conflict.employee_id and self.employee_id and conflict.employee_id != self.employee_id:
                raise UserError(_("Destination PIN belongs to a different mapped employee."))

        if transfer_mode in ("full", "profile_only", "authorize_only"):
            # These policies are IDs on the DESTINATION, never inferred from
            # a source terminal's group or country.
            authorization = _format_user_authorization(
                self.pin, authorization_timezone_id, authorization_door_id,
            )
        if transfer_mode in ("full", "profile_only"):
            if type(authorization_group_id) is not int or not 1 <= authorization_group_id <= 99:
                raise UserError(_("Enter a valid destination access group (1–99)."))

        if transfer_mode == "profile_only":
            if conflict:
                raise UserError(_("This PIN already exists on the target. Use Complete Transfer for matching users."))
            text = _format_profile(self, authorization_group_id)
            profile_command = target.queue_adms_command(
                text, _("Security PUSH: normal user profile")
            )
            if self.employee_id:
                profile_command.sudo().write({
                    "transfer_requested_by": self.env.user.id,
                    "transfer_source_user_id": self.id,
                    "transfer_employee_id": self.employee_id.id,
                    "transfer_pin": self.pin,
                    "transfer_name": self.name,
                })
            authorization_command = target.queue_adms_command(
                authorization, _("Authorize transferred user for selected time period and door"),
                depends_on=profile_command,
            )
            target.queue_adms_command(
                "DATA QUERY tablename=user,fielddesc=*,filter=Pin=%s" % self.pin,
                _("Verify transferred user and employee mapping"),
                depends_on=authorization_command,
            )
            return 3

        if transfer_mode == "full":
            if not PIN_PATTERN.fullmatch(self.pin or ""):
                raise UserError(_("The source user PIN must be 1–12 digits."))
            # Preflight the whole data set before placing even the profile in
            # the command queue; a mismatched algorithm must not leave behind
            # a half-enrolled account.
            templates = self.env["zk.device.biometric.template"].sudo().search([
                ("device_id", "=", source.id), ("pin", "=", self.pin),
                ("security_type", "in", [1, 9]),
            ], order="security_type, id")
            payloads = [_format_template(source, target, template) for template in templates]
            photo_payload = (
                _format_profile_picture(target, self.pin, self.image_1920)
                if self.image_1920 else False
            )
            if preflight_only:
                return 0
            # Queued operations are sequential. The terminal never receives
            # biodata/photo before its profile is verified by a user query.
            previous = batch_previous_command or False
            count = 0
            if not conflict:
                previous = target.queue_adms_command(
                    _format_profile(self, authorization_group_id),
                    _("Complete transfer: create normal user profile"),
                    depends_on=previous,
                )
                if self.employee_id:
                    previous.sudo().write({
                        "transfer_requested_by": self.env.user.id,
                        "transfer_source_user_id": self.id,
                        "transfer_employee_id": self.employee_id.id,
                        "transfer_pin": self.pin,
                        "transfer_name": self.name,
                    })
                count += 1
            previous = target.queue_adms_command(
                authorization, _("Complete transfer: authorize destination access"),
                depends_on=previous,
            )
            count += 1
            previous = target.queue_adms_command(
                "DATA QUERY tablename=user,fielddesc=*,filter=Pin=%s" % self.pin,
                _("Complete transfer: verify target user"),
                depends_on=previous,
            )
            # Pin/name metadata gates the NEXT command until this exact target
            # identity is freshly observed, not merely the query ACK. If the
            # destination mapping is still empty, map only after verification.
            verification_metadata = {
                "transfer_pin": self.pin,
                "transfer_name": self.name,
            }
            if self.employee_id:
                verification_metadata.update({
                    "transfer_requested_by": self.env.user.id,
                    "transfer_source_user_id": self.id,
                    "transfer_employee_id": self.employee_id.id,
                })
            previous.sudo().write(verification_metadata)
            count += 1
            for payload in payloads:
                previous = target.queue_adms_command(
                    payload, _("Complete transfer: biometric template"),
                    depends_on=previous,
                )
                count += 1
            if photo_payload:
                target.queue_adms_command(
                    photo_payload, _("Complete transfer: profile picture"),
                    depends_on=previous,
                )
                count += 1
            return count

        if not conflict:
            raise UserError(_("The normal user is not in the verified destination cache; run Complete Transfer first."))
        if transfer_mode == "authorize_only":
            target.queue_adms_command(
                authorization, _("Authorize existing target user for selected time period and door"),
            )
            return 1
        if not PIN_PATTERN.fullmatch(self.pin or ""):
            raise UserError(_("Only source users with a numeric PIN may receive biometric transfers."))
        if transfer_mode == "photo_only":
            photo_payload = _format_profile_picture(target, self.pin, self.image_1920)
            if preflight_only:
                return 0
            target.queue_adms_command(
                photo_payload, _("Transfer user profile picture (Security PUSH)"),
                depends_on=batch_previous_command,
            )
            return 1
        requested_types = [9] if transfer_mode == "face_only" else [1, 9]
        templates = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", source.id), ("pin", "=", self.pin),
            ("security_type", "in", requested_types),
        ], order="id")
        if not templates:
            if transfer_mode == "face_only":
                raise UserError(_("No cached Type 9 face template for this source PIN. Pull it before repair."))
            raise UserError(_("No supported fingerprint or face template cached for this user."))
        payloads = [_format_template(source, target, template) for template in templates]
        if preflight_only:
            return 0
        dependency = batch_previous_command or False
        for payload in payloads:
            dependency = target.queue_adms_command(
                payload, _("Security PUSH biometric template"), depends_on=dependency,
            )
        return len(payloads)

    def _queue_security_push_operations(
            self, target, operations, authorization_timezone_id, authorization_door_id,
            authorization_group_id, preflight_only=False, allow_batch_pending=False,
            batch_previous_command=None):
        """Queue only the explicitly selected Security PUSH operations.

        Command wire formats stay identical to the established transfer code;
        this method merely makes the command sequence explicit and adds a
        dependent cache readback at the operator's request.
        """
        self.ensure_one()
        valid = {"profile", "access", "fingerprint", "face", "photo", "readback"}
        selected = {key: bool(operations.get(key)) for key in valid}
        if not any(selected.values()):
            raise UserError(_("Select at least one transfer operation."))
        source = self.device_id
        if (source.device_type or "").lower() != "acc" or (target.device_type or "").lower() != "acc":
            raise UserError(_("Both terminals must use Security PUSH."))
        if not target._security_push_user_inventory_status():
            raise UserError(_("Refresh the target's user inventory before transferring."))
        if not allow_batch_pending and self.env["zk.device.command"].sudo().search_count([
            ("device_id", "=", target.id), ("state", "in", ("pending", "sent")),
        ]):
            raise UserError(_("Finish or cancel the target terminal's existing commands before transferring."))
        if not PIN_PATTERN.fullmatch(self.pin or ""):
            raise UserError(_("Only source users with a numeric PIN may be transferred to Security PUSH devices."))
        conflict = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", target.id), ("pin", "=", self.pin),
        ], limit=1)
        if conflict:
            if conflict.privilege != 0 or _validated_text(conflict.name, _("target user name")) != _validated_text(self.name, _("source user name")):
                raise UserError(_("The destination PIN belongs to a different or privileged user."))
            if conflict.employee_id and self.employee_id and conflict.employee_id != self.employee_id:
                raise UserError(_("Destination PIN is mapped to a different employee."))
        if not conflict and not selected["profile"]:
            raise UserError(_("Select Create profile if missing before transferring data to a new target PIN."))
        if selected["profile"] and not 1 <= authorization_group_id <= 99:
            raise UserError(_("Enter a valid destination access group (1–99)."))
        if selected["access"]:
            authorization = _format_user_authorization(self.pin, authorization_timezone_id, authorization_door_id)
        templates = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", source.id), ("pin", "=", self.pin),
            ("security_type", "in", [1, 9]),
        ], order="security_type, id")
        payloads = [
            (template.security_type, _format_template(source, target, template))
            for template in templates
            if (template.security_type == 1 and selected["fingerprint"])
            or (template.security_type == 9 and selected["face"])
        ]
        if selected["photo"]:
            photo_payload = _format_profile_picture(target, self.pin, self.image_1920)
        else:
            photo_payload = False
        if preflight_only:
            return 0
        previous = batch_previous_command or False
        count = 0
        if selected["profile"] and not conflict:
            previous = target.queue_adms_command(
                _format_profile(self, authorization_group_id),
                _("Transfer: create normal user profile"), depends_on=previous,
            )
            metadata = {"transfer_pin": self.pin, "transfer_name": self.name}
            if self.employee_id:
                metadata.update({"transfer_requested_by": self.env.user.id,
                                 "transfer_source_user_id": self.id,
                                 "transfer_employee_id": self.employee_id.id})
            previous.sudo().write(metadata)
            count += 1
            # This is the required identity gate for a newly-created profile,
            # not an optional diagnostics readback.
            previous = target.queue_adms_command(
                "DATA QUERY tablename=user,fielddesc=*,filter=Pin=%s" % self.pin,
                _("Transfer: verify created target user"), depends_on=previous,
            )
            previous.sudo().write(metadata)
            count += 1
        if selected["access"]:
            previous = target.queue_adms_command(
                authorization, _("Transfer: apply destination access policy"), depends_on=previous,
            )
            count += 1
        for _kind, payload in payloads:
            previous = target.queue_adms_command(payload, _("Transfer: biometric template"), depends_on=previous)
            count += 1
        if photo_payload:
            previous = target.queue_adms_command(
                photo_payload, _("Transfer: profile photo"), depends_on=previous,
            )
            count += 1
        if selected["readback"]:
            previous = target.queue_adms_command(
                "DATA QUERY tablename=user,fielddesc=*,filter=Pin=%s" % self.pin,
                _("Transfer: refresh target user cache"), depends_on=previous,
            )
            previous.sudo().write({"transfer_pin": self.pin, "transfer_name": self.name,
                                   **({"transfer_requested_by": self.env.user.id,
                                       "transfer_source_user_id": self.id,
                                       "transfer_employee_id": self.employee_id.id}
                                      if self.employee_id else {})})
            count += 1
            for bio_type in sorted({kind for kind, _payload in payloads}):
                previous = target.queue_adms_command(
                    "DATA QUERY tablename=biodata,fielddesc=*,filter=Type=%s" % bio_type,
                    _("Transfer: refresh target biometric cache"), depends_on=previous,
                )
                count += 1
            if photo_payload:
                target.queue_adms_command(
                    "DATA QUERY tablename=userpic,fielddesc=*,filter=*",
                    _("Transfer: refresh target profile photos"), depends_on=previous,
                )
                count += 1
        return count
