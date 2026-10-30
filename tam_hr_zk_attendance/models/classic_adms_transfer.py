# -*- coding: utf-8 -*-
"""Conservative, device-specific Classic/legacy ADMS transfer support.

Classic Attendance PUSH and Security PUSH use different inventory/authorization
commands. The ZKTeco Attendance PUSH specification also supports unified
``DATA UPDATE BIODATA`` (including visible-light face Type=9) on compatible
Classic firmware. Preserve native template bytes and refuse unsupported formats
or algorithm mismatches; successful ACK still requires physical readback.
"""
import base64
import binascii
import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from odoo import _, models
from odoo.exceptions import UserError


PIN = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")


def _safe_text(value, label, max_chars=80):
    value = (value or "").strip()
    if not value or len(value) > max_chars or any(ord(ch) < 32 for ch in value):
        raise UserError(_("Invalid %(label)s. Review the device-user record.", label=label))
    return value


def _classic_userpic_command(pin, image):
    """Classic Attendance PUSH DATA UPDATE USERPIC; firmware support varies."""
    if not image:
        raise UserError(_("This source user has no cached profile photograph."))
    try:
        encoded = image if isinstance(image, bytes) else image.encode("ascii")
        if len(encoded) > 3 * 1024 * 1024:
            raise ValueError("encoded image too large")
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise ValueError("image exceeds size limit")
        with Image.open(io.BytesIO(raw)) as photo:
            if photo.format not in ("JPEG", "PNG", "WEBP") or photo.width * photo.height > 8_000_000:
                raise ValueError("invalid image format/dimensions")
            photo.load()
            clean = ImageOps.exif_transpose(photo).convert("RGB")
            output = io.BytesIO()
            clean.save(output, format="JPEG", quality=85, optimize=True)
            if len(output.getvalue()) > 2 * 1024 * 1024:
                raise ValueError("converted image too large")
            base64_photo = base64.b64encode(output.getvalue()).decode("ascii")
    except (TypeError, ValueError, UnicodeError, binascii.Error, OSError,
            UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise UserError(_("The cached photograph must be a valid image of at most 2 MiB.")) from exc
    if len(base64_photo) > 2_800_000:
        raise UserError(_("The profile photo exceeds the Classic ADMS transfer limit."))
    return "DATA UPDATE USERPIC PIN=%s\tSize=%d\tContent=%s" % (
        pin, len(base64_photo), base64_photo,
    )


def _classic_face_commands(source, target, templates):
    """Return native Classic FACE or unified Type 9 BIODATA upload commands.

    These are distinct documented ZKTeco formats. Never change source bytes,
    infer a face from the profile photo, or substitute one format for another.
    Both terminals must advertise the same face algorithm before replay.
    """
    from .security_push_transfer import _format_template, _registry_algorithm

    # Two different native face encodings for the same enrollment must not
    # overwrite each other in an unattended bulk operation.
    formats = {
        "legacy" if template.template_version == "classic-face"
        else "unified" for template in templates
    }
    if len(formats) > 1:
        raise UserError(_(
            "Source contains mixed legacy FACE and unified Type 9 face records. "
            "Refresh the source enrollment and choose one native format before transferring."
        ))
    payloads = []
    for template in templates:
        if template.biometric_type != "face" or template.pin != source.pin:
            raise UserError(_("Face template identity/type does not match the source PIN."))
        if template.template_version == "classic-face" and not template.security_metadata_complete:
            source_ver, _source_limit = _registry_algorithm(source.device_id, 9)
            target_ver, target_limit = _registry_algorithm(target, 9)
            if source_ver != target_ver:
                raise UserError(_("Classic FACE algorithms differ across the two terminals."))
            encoded = template.template
            if isinstance(encoded, bytes):
                try:
                    encoded = encoded.decode("ascii")
                except UnicodeDecodeError as exc:
                    raise UserError(_("Invalid cached Classic FACE encoding.")) from exc
            try:
                raw = base64.b64decode(encoded or "", validate=True)
            except (ValueError, binascii.Error) as exc:
                raise UserError(_("Invalid cached Classic FACE base64.")) from exc
            slot = template.template_index - 10_000
            if not 0 <= slot <= 99 or template.valid != 1 or not 16 < len(raw) <= 2 * 1024 * 1024 or len(raw) != template.template_size:
                raise UserError(_("Invalid cached Classic FACE template metadata."))
            payload = "DATA UPDATE FACE PIN=%s\tFID=%d\tValid=1\tSize=%d\tTMP=%s" % (
                source.pin, slot, len(encoded), encoded,
            )
            if not target_limit or len(payload.encode("ascii")) > min(target_limit, 2_048_000):
                raise UserError(_("Classic FACE template exceeds target package limit."))
            payloads.append(payload)
        elif template.security_type == 9 and template.security_metadata_complete:
            # Reuse the native BIODATA validation (base64, slot, version,
            # format, algorithm match and target's package-size limit).
            payloads.append(_format_template(source.device_id, target, template))
        else:
            raise UserError(_(
                "Unsupported cached face format. Pull native face templates from the source device first."
            ))
    return payloads


class ZkClassicAdmsTransfer(models.Model):
    _inherit = "zk.device.user"

    def _queue_classic_adms_transfer(self, target, transfer_mode="full", operations=None,
                                     preflight_only=False, allow_batch_pending=False,
                                     batch_previous_command=None):
        self.ensure_one()
        if operations is not None:
            return self._queue_classic_adms_operations(
                target, operations, preflight_only, allow_batch_pending,
                batch_previous_command,
            )
        if (self.device_id.device_type or "").strip().lower() not in ("att", "") or (
                target.device_type or "").strip().lower() not in ("att", ""):
            raise UserError(_("Classic ADMS transfer requires two Classic-compatible devices."))
        if transfer_mode not in ("full", "photo_only", "face_only"):
            raise UserError(_(
                "Classic ADMS supports complete transfer (normal-user profile, "
                "fingerprints, native Type 9 face and optional photo), or face/photo repair."
            ))
        if not self.device_id.is_approved or not target.is_approved or target.id == self.device_id.id:
            raise UserError(_("Choose a different approved destination device."))
        if not (self.env.is_superuser() or self.env.user.has_group(
                "tam_hr_zk_attendance.group_biometric_manager")):
            raise UserError(_("Only Biometric Managers may transfer device users."))
        permitted = self.env.user.company_ids.ids
        if (self.device_id.company_id.id not in permitted or target.company_id.id not in permitted):
            raise UserError(_("You must have access to both terminal companies."))
        if not allow_batch_pending and self.env["zk.device.command"].sudo().search_count([
                ("device_id", "=", target.id), ("state", "in", ("pending", "sent"))]):
            raise UserError(_("Finish the destination's pending commands before transferring."))
        if not PIN.fullmatch(self.pin or ""):
            raise UserError(_("Classic ADMS PIN contains unsupported characters."))
        name = _safe_text(self.name, _("device user name"))
        from datetime import timedelta
        from odoo import fields
        if not target.last_user_sync_at or target.last_user_sync_at < fields.Datetime.now() - timedelta(hours=24):
            raise UserError(_(
                "Refresh destination USERINFO before transferring to this Classic terminal "
                "(last user inventory is older than 24 hours)."
            ))
        conflict = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", target.id), ("pin", "=", self.pin),
        ], limit=1)
        if conflict:
            if conflict.privilege != 0 or (conflict.name or "").strip() != name:
                raise UserError(_(
                    "Destination PIN %(pin)s belongs to a different or privileged user. "
                    "No commands were queued.", pin=self.pin,
                ))
            if conflict.employee_id and self.employee_id and conflict.employee_id != self.employee_id:
                raise UserError(_("This destination PIN is mapped to a different employee."))
        if transfer_mode in ("photo_only", "face_only") and not conflict:
            raise UserError(_("Face/photo repair requires the matching normal user in the destination cache."))

        fingerprints = self.env["zk.device.fingerprint"].sudo().search([
            ("device_id", "=", self.device_id.id), ("pin", "=", self.pin),
        ], order="finger_id") if transfer_mode == "full" else self.env["zk.device.fingerprint"].browse()
        faces = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", self.device_id.id), ("pin", "=", self.pin),
            ("biometric_type", "=", "face"),
        ], order="template_index, id") if transfer_mode in ("full", "face_only") else self.env["zk.device.biometric.template"].browse()
        # Preflight entire batch *before* queueing any profile, fingerprint,
        # face or photo writes. Unknown/incomplete face formats are rejected,
        # not silently dropped from a requested Complete Transfer.
        face_commands = _classic_face_commands(self, target, faces)
        if transfer_mode == "face_only" and not face_commands:
            raise UserError(_("No compatible cached visible-light face (Type 9) for this PIN. Pull face templates first."))
        fp_commands = []
        for fp in fingerprints:
            if not isinstance(fp.finger_id, int) or not 0 <= fp.finger_id <= 19:
                raise UserError(_("Invalid cached fingerprint slot for PIN %(pin)s.", pin=self.pin))
            template = fp.template.decode("ascii") if isinstance(fp.template, bytes) else fp.template
            if not template or len(template) > 40_000 or any(ch in template for ch in ("\t", "\r", "\n")):
                raise UserError(_("Invalid cached fingerprint payload for PIN %(pin)s.", pin=self.pin))
            if not fp.template_size or fp.template_size > 32_000:
                raise UserError(_("Invalid cached fingerprint length for PIN %(pin)s.", pin=self.pin))
            fp_commands.append(
                "DATA FP PIN=%s\tFID=%d\tSize=%d\tValid=%d\tTMP=%s" % (
                    self.pin, fp.finger_id, fp.template_size, int(fp.valid), template,
                )
            )
        photo_payload = _classic_userpic_command(self.pin, self.image_1920) if (
            transfer_mode == "photo_only" or (transfer_mode == "full" and self.image_1920)
        ) else False
        if preflight_only:
            return 0

        preceding = batch_previous_command or False
        count = 0
        if transfer_mode == "full":
            if not conflict:
                preceding = target.queue_adms_command(
                    "DATA USER PIN=%s\tName=%s\tPri=0\tPasswd=\tCard=\tGrp=1\tTZ=" % (self.pin, name),
                    _("Classic transfer: create normal user"), depends_on=preceding,
                )
                if self.employee_id:
                    preceding.sudo().write({
                        "transfer_requested_by": self.env.user.id,
                        "transfer_source_user_id": self.id,
                        "transfer_employee_id": self.employee_id.id,
                        "transfer_pin": self.pin,
                        "transfer_name": name,
                    })
                count += 1
            preceding = target.queue_adms_command(
                "DATA QUERY USERINFO PIN=%s" % self.pin,
                _("Complete transfer: verify target user"), depends_on=preceding,
            )
            metadata = {"transfer_pin": self.pin, "transfer_name": name}
            if self.employee_id:
                metadata.update({
                    "transfer_requested_by": self.env.user.id,
                    "transfer_source_user_id": self.id,
                    "transfer_employee_id": self.employee_id.id,
                })
            preceding.sudo().write(metadata)
            count += 1
            for payload in fp_commands:
                preceding = target.queue_adms_command(
                    payload, _("Classic transfer: fingerprint template"), depends_on=preceding,
                )
                count += 1
        if transfer_mode in ("full", "face_only"):
            for payload in face_commands:
                preceding = target.queue_adms_command(
                    payload, _("Classic transfer: visible-light face template (Type 9)"),
                    depends_on=preceding,
                )
                count += 1
        if photo_payload:
            preceding = target.queue_adms_command(
                photo_payload, _("Classic transfer: profile picture (firmware dependent)"),
                depends_on=preceding,
            )
            count += 1
        return count

    def _queue_classic_adms_operations(
            self, target, operations, preflight_only=False, allow_batch_pending=False,
            batch_previous_command=None):
        """Queue only checked Classic ADMS operations, preserving wire formats."""
        self.ensure_one()
        selected = {key: bool(operations.get(key)) for key in (
            "profile", "access", "fingerprint", "face", "photo", "readback",
        )}
        # Classic ADMS has no separately verified per-user access command.
        selected["access"] = False
        if not any(selected.values()):
            raise UserError(_("Select at least one transfer operation."))
        if (self.device_id.device_type or "").strip().lower() not in ("att", "") or (
                target.device_type or "").strip().lower() not in ("att", ""):
            raise UserError(_("Classic ADMS transfer requires two Classic-compatible devices."))
        if not allow_batch_pending and self.env["zk.device.command"].sudo().search_count([
                ("device_id", "=", target.id), ("state", "in", ("pending", "sent"))]):
            raise UserError(_("Finish the destination's pending commands before transferring."))
        if not PIN.fullmatch(self.pin or ""):
            raise UserError(_("Classic ADMS PIN contains unsupported characters."))
        name = _safe_text(self.name, _("device user name"))
        from datetime import timedelta
        from odoo import fields
        if not target.last_user_sync_at or target.last_user_sync_at < fields.Datetime.now() - timedelta(hours=24):
            raise UserError(_("Refresh destination USERINFO before transferring to this Classic terminal."))
        conflict = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", target.id), ("pin", "=", self.pin),
        ], limit=1)
        if conflict and (conflict.privilege != 0 or (conflict.name or "").strip() != name):
            raise UserError(_("The destination PIN belongs to a different or privileged user."))
        if not conflict and not selected["profile"]:
            raise UserError(_("Select Create profile if missing before transferring data to a new target PIN."))
        fingerprints = self.env["zk.device.fingerprint"].sudo().search([
            ("device_id", "=", self.device_id.id), ("pin", "=", self.pin),
        ], order="finger_id") if selected["fingerprint"] else self.env["zk.device.fingerprint"].browse()
        faces = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", self.device_id.id), ("pin", "=", self.pin),
            ("biometric_type", "=", "face"),
        ], order="template_index, id") if selected["face"] else self.env["zk.device.biometric.template"].browse()
        face_commands = _classic_face_commands(self, target, faces) if selected["face"] else []
        fp_commands = []
        for fp in fingerprints:
            if not isinstance(fp.finger_id, int) or not 0 <= fp.finger_id <= 19:
                raise UserError(_("Invalid cached fingerprint slot for PIN %(pin)s.", pin=self.pin))
            template = fp.template.decode("ascii") if isinstance(fp.template, bytes) else fp.template
            if not template or len(template) > 40_000 or any(ch in template for ch in ("\t", "\r", "\n")) or not fp.template_size or fp.template_size > 32_000:
                raise UserError(_("Invalid cached fingerprint payload for PIN %(pin)s.", pin=self.pin))
            fp_commands.append("DATA FP PIN=%s\tFID=%d\tSize=%d\tValid=%d\tTMP=%s" % (
                self.pin, fp.finger_id, fp.template_size, int(fp.valid), template))
        photo_payload = _classic_userpic_command(self.pin, self.image_1920) if selected["photo"] else False
        if preflight_only:
            return 0
        previous = batch_previous_command or False
        count = 0
        metadata = {"transfer_pin": self.pin, "transfer_name": name}
        if self.employee_id:
            metadata.update({"transfer_requested_by": self.env.user.id,
                             "transfer_source_user_id": self.id,
                             "transfer_employee_id": self.employee_id.id})
        if selected["profile"] and not conflict:
            previous = target.queue_adms_command(
                "DATA USER PIN=%s\tName=%s\tPri=0\tPasswd=\tCard=\tGrp=1\tTZ=" % (self.pin, name),
                _("Transfer: create normal user"), depends_on=previous)
            previous.sudo().write(metadata)
            count += 1
            previous = target.queue_adms_command(
                "DATA QUERY USERINFO PIN=%s" % self.pin,
                _("Transfer: verify created target user"), depends_on=previous)
            previous.sudo().write(metadata)
            count += 1
        for payload in fp_commands:
            previous = target.queue_adms_command(payload, _("Transfer: fingerprint template"), depends_on=previous)
            count += 1
        for payload in face_commands:
            previous = target.queue_adms_command(payload, _("Transfer: visible-light face template (Type 9)"), depends_on=previous)
            count += 1
        if photo_payload:
            previous = target.queue_adms_command(photo_payload, _("Transfer: profile photo (firmware dependent)"), depends_on=previous)
            count += 1
        if selected["readback"]:
            previous = target.queue_adms_command(
                "DATA QUERY USERINFO PIN=%s" % self.pin,
                _("Transfer: refresh target user cache"), depends_on=previous)
            previous.sudo().write(metadata)
            count += 1
            if selected["face"]:
                target.queue_adms_command(
                    "DATA QUERY BIODATA Type=9", _("Transfer: refresh target face cache"),
                    depends_on=previous)
                count += 1
        return count
