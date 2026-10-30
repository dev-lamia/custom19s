# -*- coding: utf-8 -*-
import base64
import binascii
import datetime
import logging
import re
import secrets

import pytz

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

from .device_metadata import extract_registry_capabilities, extract_versions

from .security_push_codec import (
    MAX_BODY_BYTES, SUPPORTED_TABLES, parse_tabledata, decode_biodata_record,
    decode_userpic_record, server_biometric_support,
)

_logger = logging.getLogger(__name__)


class ZKPushController(http.Controller):
    """ZKTeco ADMS / Security PUSH receiver.

    The controller intentionally supports both the classic attendance PUSH flow
    (``ATTLOG``) and the Security PUSH 3.1.2 flow used by access-control devices
    (``DeviceType=acc``), which registers through ``/iclock/registry`` and then
    downloads configuration through ``/iclock/push``.
    """

    SECURITY_PUSH_VERSION = "3.1.2"
    RTLOG_ATTENDANCE_EVENTS = {
        "0", "1", "2", "3",          # normal verified access
        "14", "15", "16", "17", "18", "19",  # biometric variants
        "203", "232",                 # multi-user / verification passed
    }
    KNOWN_PUNCH_TYPES = {"0", "1", "2", "3", "4", "5", "255"}
    KNOWN_VERIFY_TYPES = {"0", "1", "2", "3", "4", "5", "6", "15", "20", "25", "255"}

    def _resp(self, body="OK", status=200, content_type="text/plain; charset=utf-8"):
        return request.make_response(
            body,
            headers=[("Content-Type", content_type)],
            status=status,
        )

    def _parse_kv_line(self, line, separators=("\t",)):
        """Parse a ZKTeco key=value record into a case-insensitive dict."""
        parts = [line]
        for sep in separators:
            expanded = []
            for part in parts:
                expanded.extend(part.split(sep))
            parts = expanded

        result = {}
        for part in parts:
            part = (part or "").strip()
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            result[key.strip().lstrip("~").lower()] = value.strip()
        return result

    def _parse_registry_payload(self, raw):
        # Security PUSH registry bodies are normally comma-separated key=value.
        return self._parse_kv_line(raw or "", separators=(",", "\r", "\n"))

    def _log_payload_summary(self, sn, table, raw):
        """Log only record-type counts, never personal/biometric photo bytes."""
        if table == "OPERLOG":
            user_count = sum(1 for line in raw.splitlines() if line.startswith("USER "))
            fp_count = sum(1 for line in raw.splitlines() if line.startswith("FP "))
            picture_count = sum(1 for line in raw.splitlines() if line.startswith("USERPIC "))
            face_count = sum(1 for line in raw.splitlines() if line.startswith(("FACE ", "BIODATA ")))
            _logger.info(
                "ZK CDATA POST: SN=%s table=%s user_records=%s fingerprint_records=%s picture_records=%s face_records=%s",
                sn, table, user_count, fp_count, picture_count, face_count,
            )
            return
        _logger.debug("ZK CDATA POST: SN=%s table=%s bytes=%s", sn, table, len(raw or ""))

    @staticmethod
    def _classic_legacy_face(values):
        """Parse native legacy Classic FACE bytes without transforming enrollment.

        Legacy FACE and unified visible-light Type=9 are different native
        formats. Keep a distinctive version marker so the sender chooses the
        matching wire command and never relabels legacy FACE as BIODATA.
        """
        pin = (values.get("pin") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", pin):
            raise ValueError("Invalid Classic FACE PIN")
        try:
            fid = int(values["fid"])
            size = int(values["size"])
            valid = int(values.get("valid", "1"))
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("Invalid Classic FACE metadata") from exc
        encoded = (values.get("tmp") or "").strip()
        if not 0 <= fid <= 99 or valid != 1 or not 0 < size <= 2_800_000 or size != len(encoded):
            raise ValueError("Invalid Classic FACE slot/size")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid Classic FACE base64") from exc
        if not 16 < len(raw) <= 2 * 1024 * 1024:
            raise ValueError("Invalid Classic FACE body size")
        return {
            "pin": pin, "biometric_type": "face", "template_index": 10_000 + fid,
            "template_version": "classic-face", "valid": 1,
            "template_size": len(raw), "template": encoded,
            "security_type": 0, "security_metadata_complete": False,
        }

    def _store_classic_biodata(self, device, raw):
        """Persist bounded native Type 9 records from approved Classic ATT.

        ATT unified responses arrive through /iclock/cdata?table=BIODATA,
        unlike Security PUSH query packages from /iclock/querydata.
        """
        if not device or not device.is_approved or (device.device_type or "").lower() not in ("att", ""):
            raise ValueError("Device not approved for Classic biodata")
        if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError("Classic BIODATA payload is too large")
        records = parse_tabledata(raw, "biodata")
        for values in records:
            if str(values.get("type", "")) != "9":
                raise ValueError("Only visible-light face Type 9 may be cached from Classic BIODATA")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", values.get("pin") or ""):
                raise ValueError("Invalid Classic BIODATA PIN")
            request.env["zk.device.biometric.template"].sudo().upsert_from_adms(
                device, decode_biodata_record(values),
            )
        return len(records)

    def _store_operlog_payload(self, device, raw, received_user_pins=None):
        """Persist Classic USER/FP/USERPIC and native face records privately.

        USERPIC is a display photograph; FACE/BIODATA carry recognition data.
        Neither content is logged, and malformed packets cause rollback.
        """
        users = 0
        fingerprints = 0
        pictures = 0
        for original_line in raw.splitlines():
            line = (original_line or "").strip()
            if line.startswith("USER "):
                values = self._parse_kv_line(line[5:], separators=("\t",))
                pin = values.get("pin")
                if pin:
                    values["pin"] = str(pin).strip()
                    request.env["zk.device.user"].sudo().upsert_from_adms(device, values)
                    users += 1
                    if received_user_pins is not None:
                        received_user_pins.add(values["pin"])
            elif line.startswith("FP "):
                values = self._parse_kv_line(line[3:], separators=("\t",))
                if all(values.get(key) not in (None, "") for key in ("pin", "fid", "size", "tmp")):
                    values["pin"] = str(values["pin"]).strip()
                    request.env["zk.device.fingerprint"].sudo().upsert_from_adms(device, values)
                    request.env["zk.device.biometric.template"].sudo().upsert_from_adms(device, {
                        "pin": values["pin"], "biometric_type": "fingerprint",
                        "template_index": values["fid"], "template_version": values.get("ver"),
                        "valid": values.get("valid"), "template_size": values["size"], "template": values["tmp"],
                    })
                    fingerprints += 1
            elif line.startswith("BIODATA "):
                values = self._parse_kv_line(line[8:], separators=("\t",))
                if str(values.get("type", "")) != "9":
                    raise ValueError("Unsupported Classic BIODATA type in OPERLOG")
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", values.get("pin") or ""):
                    raise ValueError("Invalid Classic BIODATA PIN")
                request.env["zk.device.biometric.template"].sudo().upsert_from_adms(
                    device, decode_biodata_record(values),
                )
            elif line.startswith("FACE "):
                values = self._parse_kv_line(line[5:], separators=("\t",))
                request.env["zk.device.biometric.template"].sudo().upsert_from_adms(
                    device, self._classic_legacy_face(values),
                )
            elif line.startswith("USERPIC "):
                # Attendance PUSH User Photo: USERPIC PIN=...\tFileName=...\tSize=...\tContent=...
                # Use the existing strict JPEG/base64 validator, bounded to
                # 2 MiB decoded. An invalid image must never be acknowledged
                # as imported, and its contents must never enter request logs.
                values = self._parse_kv_line(line[8:], separators=("\t",))
                photo = decode_userpic_record(values)
                user_model = request.env["zk.device.user"].sudo()
                device_user = user_model.search([
                    ("device_id", "=", device.id),
                    ("pin", "=", photo["pin"]),
                ], limit=1)
                if not device_user:
                    # Like Security PUSH USERPIC: do not create an employee or
                    # assign a privilege; the USER record supplies its name.
                    device_user = user_model.create({
                        "device_id": device.id,
                        "pin": photo["pin"],
                    })
                device_user.write({"image_1920": photo["image_1920"]})
                pictures += 1
        return users, fingerprints, pictures

    def _store_security_tabledata(self, device, tablename, raw, expected_count=None):
        """Process one Security PUSH table-data package atomically.

        Only an approved, already registered access-control device may write
        these records. The PIN remains local to this device; no HR employee
        is auto-created or mapped. Biometric templates are never logged.
        """
        if not device.is_approved or (device.device_type or "").lower() != "acc":
            raise ValueError("Unapproved or non-Security PUSH device")
        records = parse_tabledata(raw, tablename)
        if expected_count is not None and expected_count != len(records):
            raise ValueError("Security PUSH record count does not match package")

        for values in records:
            if tablename == "user":
                request.env["zk.device.user"].sudo().upsert_from_adms(device, {
                    "pin": values["pin"],
                    "name": values.get("name"),
                    "privilege": values.get("privilege", "0"),
                    "passwd": values.get("password"),
                    "card": values.get("cardno") or values.get("card"),
                    "grp": values.get("group"),
                    "tz": values.get("tz"),
                })
            elif tablename == "biodata":
                request.env["zk.device.biometric.template"].sudo().upsert_from_adms(
                    device, decode_biodata_record(values),
                )
            elif tablename == "userpic":
                photo = decode_userpic_record(values)
                users = request.env["zk.device.user"].sudo()
                user = users.search([
                    ("device_id", "=", device.id), ("pin", "=", photo["pin"]),
                ], limit=1)
                if not user:
                    # Photo may precede USER tabledata on the first push.
                    # Create only an unmapped, non-privileged device-local stub;
                    # a subsequent USER packet supplies identity and group.
                    # Never create or guess a real hr.employee from a PIN.
                    user = users.create({"device_id": device.id, "pin": photo["pin"]})
                user.write({"image_1920": photo["image_1920"]})
        if tablename == "user":
            device.write({"last_user_sync_at": fields.Datetime.now()})
        return len(records)

    def _security_tabledata_request(self, params, raw, query_only=False):
        """Validate inbound tabledata and acknowledge its *persisted* row count.

        Query packages must match a sent/done command on the same device with
        the exact expected table (and template Type), preventing unsolicited
        command completion or cross-device data association.
        """
        values = {str(key).lower(): str(value) for key, value in params.items()}
        sn = values.get("sn", "").strip()
        table = values.get("tablename", "").strip().lower()
        if not sn or table not in SUPPORTED_TABLES:
            return self._resp("Unsupported Security PUSH table", status=400)
        if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
            return self._resp("Package too large", status=413)
        device = request.env["zk.device"].sudo().search([
            ("serial_number", "=", sn),
        ], limit=1)
        if not device or not device.is_approved or (device.device_type or "").lower() != "acc":
            return self._resp("Device is not approved for Security PUSH", status=403)

        command = False
        package_index = package_total = 1
        if query_only:
            if values.get("type", "").lower() != "tabledata":
                return self._resp("Unsupported query response type", status=400)
            try:
                cmd_id = int(values["cmdid"])
                package_total = int(values.get("packcnt") or 1)
                package_index = int(values.get("packidx") or 1)
            except (KeyError, ValueError, TypeError):
                return self._resp("Invalid query command or package number", status=400)
            if not (cmd_id > 0 and 1 <= package_index <= package_total <= 100000):
                return self._resp("Invalid Security PUSH package index", status=400)
            command = request.env["zk.device.command"].sudo().search([
                ("device_id", "=", device.id),
                ("command_id", "=", cmd_id),
                ("state", "in", ["sent", "done", "failed"]),
            ], limit=1)
            if command and command.state == "failed" and table != "userpic":
                command = False
            if not command or not command.command.startswith(
                "DATA QUERY tablename=%s," % table
            ):
                return self._resp("Security PUSH query does not match command", status=409)
        try:
            expected_count = int(values["count"]) if "count" in values else None
            if expected_count is not None and expected_count < 0:
                raise ValueError("Negative record count")
            # Verify the returned biometric Type is the requested type. Query
            # syntax can be extended by firmware but the first Type is stable.
            if command and table == "biodata":
                requested_type = command.command.split("filter=Type=", 1)[-1]
                if not requested_type.isdigit():
                    raise ValueError("Unsupported biometric query filter")
                for record in parse_tabledata(raw, table):
                    if record.get("type") != requested_type:
                        raise ValueError("Biometric type does not match requested type")
            # Keep each package atomic. Odoo controllers that catch errors and
            # return HTTP 4xx/5xx must explicitly roll back partial ORM writes.
            with request.env.cr.savepoint():
                count = self._store_security_tabledata(device, table, raw, expected_count)
                if command:
                    update = {"last_payload_at": fields.Datetime.now()}
                    if table == "userpic":
                        # This records received pictures independently of the
                        # command ACK (firmware sometimes returns -1 afterward).
                        update["received_log_count"] = command.received_log_count + count
                    if command.state == "sent" and package_index == package_total:
                        # Some firmwares omit /devicecmd ACK after their final
                        # package; do not leave a successful query 'sent' forever.
                        update.update({"state": "done", "return_code": "payload_received",
                                       "completed_at": fields.Datetime.now()})
                    command.write(update)
            _logger.info("ZK Security PUSH stored: SN=%s table=%s records=%s package=%s/%s",
                         sn, table, count, package_index, package_total)
            return self._resp("%s=%s" % (table, count))
        except (ValueError, TypeError):
            _logger.warning("ZK Security PUSH package validation failed: SN=%s table=%s", sn, table)
            return self._resp("Invalid Security PUSH package", status=400)
        except Exception:
            # 5xx instead of 200 forces a compatible device to retry; Odoo
            # rolls back the transaction on an unhandled storage error.
            _logger.exception("ZK Security PUSH persistence failed: SN=%s table=%s", sn, table)
            return self._resp("Storage failure", status=500)

    def _get_or_create_device(self, sn, extra_vals=None, touch_last_seen=False):
        """Get/create a device without turning it into a high-contention hot row.

        ADMS devices can send GETREQUEST, ATTLOG and RTLOG requests concurrently.
        Writing ``last_seen`` on every request makes all workers compete for the
        same ``zk.device`` row under PostgreSQL/Odoo transaction isolation.
        Only low-frequency handshake/registration paths should request a touch.
        """
        if not sn:
            return request.env["zk.device"]

        ZkDevice = request.env["zk.device"].sudo()
        device = ZkDevice.search([("serial_number", "=", sn)], limit=1)
        if not device:
            device = ZkDevice.search([("name", "=", sn)], limit=1)
            if device:
                device.write({"serial_number": sn, "name": _("Device %(serial)s", serial=sn)})
        remote_ip = request.httprequest.remote_addr

        if not device:
            registration_company = ZkDevice._adms_registration_company()
            if not registration_company:
                raise RuntimeError("No company is available for ADMS device registration.")
            vals = {
                "name": "Device %s" % sn,
                "serial_number": sn,
                "company_id": registration_company.id,
                "is_approved": False,
                "ip_address": remote_ip,
                "tz": "UTC",
                "allow_push": False,
                "last_seen": fields.Datetime.now(),
            }
            if extra_vals:
                vals.update({key: value for key, value in extra_vals.items() if value is not None})
            return ZkDevice.create(vals)

        vals = {}
        if remote_ip and device.ip_address != remote_ip:
            vals["ip_address"] = remote_ip
        # Record a heartbeat at most once every 30 seconds, avoiding a hot row
        # while still giving users a reliable online/offline status.
        if touch_last_seen:
            now = fields.Datetime.now()
            if not device.last_seen or device.last_seen < now - datetime.timedelta(seconds=30):
                vals["last_seen"] = now
        if extra_vals:
            for key, value in extra_vals.items():
                if value is not None and device[key] != value:
                    vals[key] = value
        if vals:
            device.write(vals)
        return device

    @staticmethod
    def _classic_trans_flag(device):
        """Advertise safe automatic user-photo pushes on approved Classic ADMS.

        The tenth digit in the documented Classic PUSH TransFlag controls
        USERPIC upload. This does not cause a historical photo dump and is
        never used for Security PUSH (acc) or unapproved devices. The terminal
        refreshes its options through a protocol CHECK, without unplugging it.
        """
        return (
            "1111000001"
            if device and device.is_approved
            and (device.device_type or "").strip().lower() in ("att", "")
            else "1111000000"
        )

    def _security_push_config(self, device):
        # Only negotiate capabilities the server actually supports. The
        # terminal also computes the intersection with its own type mask.
        # An empty/malformed registry fails closed to all-zero masks.
        bio_data, bio_photo = server_biometric_support(device.registry_payload)
        session_id = device.session_id
        if not session_id:
            session_id = secrets.token_hex(16)
            device.sudo().write({"session_id": session_id})

        return (
            f"ServerVersion={self.SECURITY_PUSH_VERSION}\r\n"
            "ServerName=Odoo\r\n"
            f"PushVersion={self.SECURITY_PUSH_VERSION}\r\n"
            f"PushProtVer={self.SECURITY_PUSH_VERSION}\r\n"
            "ErrorDelay=60\r\n"
            "RequestDelay=30\r\n"
            "TransTimes=00:00;14:05\r\n"
            "TransInterval=1\r\n"
            "TransTables=User Transaction\r\n"
            f"MultiBioDataSupport={bio_data}\r\n"
            f"MultiBioPhotoSupport={bio_photo}\r\n"
            "Realtime=1\r\n"
            f"SessionID={session_id}\r\n"
            "TimeoutSec=10\r\n"
        )

    def _save_version_info(self, device, versions, source, command=None):
        """Record only reported version fields; never persist unfiltered INFO data.

        This routine is intentionally no-op if the approved device sends no
        parseable version identifiers (Return=0 alone proves nothing).
        """
        if not device or not device.is_approved or not versions:
            return False
        data = {name: value for name, value in versions.items()
                if name in ("firmware_version", "push_version") and value}
        if not data:
            return False
        data.update({"metadata_source": source, "last_metadata_at": fields.Datetime.now()})
        device.sudo().write(data)
        if command:
            summary = "; ".join(
                "%s=%s" % (key, versions[key])
                for key in ("firmware_version", "push_version") if key in versions
            )
            command.sudo().write({"version_response": summary[:245]})
        _logger.info("ZK version metadata refreshed: SN=%s source=%s fields=%s",
                     device.serial_number, source, ",".join(sorted(versions)))
        return True

    # ----------------------------
    # /iclock/cdata
    # ----------------------------
    @http.route("/iclock/cdata", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_cdata(self, **params):
        # GET is used by devices for options=all during ADMS handshake.
        if request.httprequest.method == "GET":
            sn = (params.get("SN") or "").strip()
            options = (params.get("options") or "").strip().lower()
            push_version = (params.get("pushver") or "").strip()
            device_type = (params.get("DeviceType") or "").strip()
            _logger.debug("ZK CDATA GET: SN=%s options=%s", sn, options)

            if options == "all":
                # pushver is the classic ADMS handshake revision. It MUST NOT
                # replace the installed PushVersion returned in metadata.
                metadata = {}
                if push_version:
                    metadata["adms_protocol_version"] = push_version[:96]
                if device_type in ("att", "acc"):
                    metadata["device_type"] = device_type
                device = self._get_or_create_device(sn, metadata,
                    touch_last_seen=True) if sn else False

                tz_offset = device._get_adms_timezone_offset() if device else "0"
                trans_flag = self._classic_trans_flag(device)
                if trans_flag.endswith("1"):
                    _logger.info("ZK Classic USERPIC upload advertised: SN=%s", sn)
                op_stamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                body = (
                    f"GET OPTION FROM: {sn}\r\n"
                    "Stamp=9999\r\n"
                    f"OpStamp={op_stamp}\r\n"
                    "ErrorDelay=60\r\n"
                    "Delay=30\r\n"
                    "RequestDelay=30\r\n"
                    "ResLogDay=18250\r\n"
                    "ResLogDelCount=10000\r\n"
                    "ResLogCount=50000\r\n"
                    "TransTimes=00:00;14:05\r\n"
                    "TransInterval=1\r\n"
                    f"TransFlag={trans_flag}\r\n"
                    "TransTables=User Transaction\r\n"
                    f"TimeZone={tz_offset}\r\n"
                    f"PushProtVer={self.SECURITY_PUSH_VERSION}\r\n"
                    "Realtime=1\r\n"
                    "Encrypt=0\r\n"
                )
                return self._resp(body)

            if sn:
                self._get_or_create_device(sn)
            return self._resp("OK")

        # Security PUSH sends unsolicited registered-user and biometric updates
        # as tabledata through /cdata. Keep classic ADMS parsing below intact.
        if (params.get("table") or "").lower() == "tabledata":
            raw = request.httprequest.get_data(as_text=True) or ""
            return self._security_tabledata_request(params, raw)

        # POST contains ATTLOG / RTLOG / OPERLOG / USERINFO / device payloads.
        sn = (params.get("SN") or "").strip()
        table = (params.get("table") or "").upper().strip()
        raw = request.httprequest.get_data(as_text=True) or ""
        # Prevent a single large Classic OPERLOG upload from consuming unbounded
        # parser/memory resources. Existing ATTLOG/RTLOG behavior is unchanged.
        if table == "OPERLOG" and len(raw.encode("utf-8")) > MAX_BODY_BYTES:
            _logger.warning("ZK OPERLOG rejected (too large): SN=%s", sn)
            return self._resp("OPERLOG too large", status=413)
        self._log_payload_summary(sn, table, raw)

        device = self._get_or_create_device(sn, touch_last_seen=True) if sn else request.env["zk.device"]

        if table == "BIODATA":
            # Classic native BIODATA cannot be passed through the Security
            # PUSH /iclock/querydata handler; that handler requires ACC.
            if not device or not device.is_approved or (device.device_type or "").lower() not in ("att", ""):
                return self._resp("Classic BIODATA device not approved", status=403)
            try:
                with request.env.cr.savepoint():
                    records = self._store_classic_biodata(device, raw)
                    if records:
                        device.complete_query_from_payload("DATA QUERY BIODATA")
                _logger.info("ZK Classic BIODATA stored: SN=%s face_records=%s", sn, records)
                return self._resp("OK")
            except ValueError:
                _logger.warning("ZK Classic BIODATA rejected invalid metadata (SN=%s)", sn)
                return self._resp("Invalid Classic BIODATA", status=400)
            except Exception:
                _logger.exception("ZK Classic BIODATA persistence failed (SN=%s)", sn)
                return self._resp("ERROR", status=500)

        if table == "OPTIONS" and device and device.is_approved:
            # The device often sends OPTIONS immediately after options=all.
            # Its body may contain passwords/addresses: parse an allowlist,
            # do not log or retain it wholesale.
            versions = extract_versions(raw)
            self._save_version_info(device, versions, "CDATA OPTIONS")

        if table == "OPERLOG" and raw.strip() and device and device.is_approved:
            try:
                user_pins = set()
                # If any row fails (including an invalid image), roll back this
                # packet before returning an error to the terminal for retry.
                with request.env.cr.savepoint():
                    users, fingerprints, pictures = self._store_operlog_payload(
                        device, raw, received_user_pins=user_pins,
                    )
                    if users:
                        device.write({"last_user_sync_at": fields.Datetime.now()})
                        device.complete_query_from_payload(
                            "DATA QUERY USERINFO", received_user_pins=user_pins,
                        )
                _logger.info(
                    "ZK OPERLOG stored: users=%s fingerprints=%s pictures=%s (SN=%s)",
                    users, fingerprints, pictures, sn,
                )
            except ValueError:
                _logger.warning("ZK OPERLOG rejected invalid record (SN=%s)", sn)
                return self._resp("Invalid OPERLOG record", status=400)
            except Exception:
                _logger.exception("ZK OPERLOG store failed (SN=%s)", sn)
                return self._resp("ERROR", status=500)

        if table in {"ATTLOG", "RTLOG"} and raw.strip():
            try:
                created, skipped, unmapped = self._store_attendance_payload(device, raw, table)
                log_method = _logger.warning if unmapped else _logger.info
                log_method(
                    "ZK %s stored: created=%s skipped=%s unmapped=%s (SN=%s)",
                    table, created, skipped, unmapped, sn,
                )
                if device:
                    device.record_attendance_payload(created, skipped, unmapped)
                    device.complete_query_from_payload("DATA QUERY ATTLOG")
                return self._resp("OK")
            except Exception:
                # Do not acknowledge a persistence failure as successful. Returning
                # 500 lets compatible firmware retry rather than silently losing data.
                _logger.exception("ZK %s store failed (SN=%s)", table, sn)
                return self._resp("ERROR", status=500)

        return self._resp("OK")

    @http.route("/iclock/querydata", type="http", auth="none", methods=["POST"], csrf=False)
    def iclock_querydata(self, **params):
        """Receive Security PUSH DATA QUERY packages (one table per command)."""
        raw = request.httprequest.get_data(as_text=True) or ""
        return self._security_tabledata_request(params, raw, query_only=True)

    # ----------------------------
    # Security PUSH registration
    # ----------------------------
    @http.route("/iclock/registry", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_registry(self, **params):
        sn = (params.get("SN") or "").strip()
        raw = request.httprequest.get_data(as_text=True) or ""
        registry = self._parse_registry_payload(raw)
        # Registry may contain credential-like data. Never print its body.
        _logger.info("ZK REGISTRY: SN=%s bytes=%s", sn, len(raw))

        if not sn:
            return self._resp("Missing SN", status=400)

        metadata = {
            "registry_payload": raw or False,
            "last_registry_at": fields.Datetime.now(),
        }
        if registry.get("devicetype") in ("att", "acc"):
            metadata["device_type"] = registry["devicetype"]
        if registry.get("devicename"):
            metadata["device_name"] = registry["devicename"][:96]
        if registry.get("pushver"):
            metadata["adms_protocol_version"] = registry["pushver"][:96]
        device = self._get_or_create_device(sn, metadata, touch_last_seen=True)
        versions = extract_versions(raw)
        self._save_version_info(device, versions, "Security PUSH registry")
        capabilities = extract_registry_capabilities(raw)
        if capabilities:
            device.sudo().write(capabilities)

        vals = {}
        if not device.registry_code:
            vals["registry_code"] = secrets.token_hex(8)
        if not device.session_id:
            vals["session_id"] = secrets.token_hex(16)
        if vals:
            device.write(vals)

        return self._resp(
            f"RegistryCode={device.registry_code}\r\n",
            content_type="application/push; charset=utf-8",
        )

    @http.route("/iclock/push", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_push(self, **params):
        """Return Security PUSH 3.1.2 configuration after registration."""
        sn = (params.get("SN") or "").strip()
        raw = request.httprequest.get_data(as_text=True) or ""
        _logger.debug("ZK PUSH CONFIG: SN=%s bytes=%s", sn, len(raw))

        if not sn:
            return self._resp("Missing SN", status=400)

        device = self._get_or_create_device(sn, touch_last_seen=True)
        if not device.registry_code:
            device.write({
                "registry_code": secrets.token_hex(8),
                "session_id": device.session_id or secrets.token_hex(16),
            })

        return self._resp(
            self._security_push_config(device),
            content_type="application/push; charset=utf-8",
        )

    # ----------------------------
    # /iclock/getrequest
    # ----------------------------
    @http.route("/iclock/getrequest", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_getrequest(self, **params):
        sn = (params.get("SN") or "").strip()
        _logger.debug("ZK GETREQUEST: SN=%s", sn)
        if sn:
            device = self._get_or_create_device(sn, touch_last_seen=True)
            command = device.next_adms_command() if device.is_approved else False
            if command:
                # Do not log command content: a fingerprint command contains a
                # biometric template. The device initiated this request.
                _logger.info("ZK ADMS command delivered: SN=%s command_id=%s", sn, command.command_id)
                return self._resp("C:%s:%s\r\n" % (command.command_id, command.command))
        return self._resp("OK")

    @http.route("/iclock/devicecmd", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_devicecmd(self, **params):
        sn = (params.get("SN") or "").strip()
        raw = request.httprequest.get_data(as_text=True) or ""
        _logger.debug("ZK DEVICECMD ACK: SN=%s", sn)
        if sn:
            device = self._get_or_create_device(sn, touch_last_seen=True)
            records = [{str(key).lower(): value for key, value in params.items()}]
            for line in raw.splitlines():
                values = self._parse_kv_line(line, separators=("&", "\t"))
                if values:
                    records.append(values)
            reply_ids = {
                str(item.get("id") or item.get("cmdid"))
                for item in records
                if str(item.get("id") or item.get("cmdid") or "").isdigit()
            }
            for record in records:
                command_id = record.get("id") or record.get("cmdid")
                if not (command_id and str(command_id).isdigit()):
                    continue
                # Only bind diagnostic content to its own sent command on this
                # device. Never accept version fields attached to an unrelated
                # fingerprint, user, restart or attendance command.
                cmd = request.env["zk.device.command"].sudo().search([
                    ("device_id", "=", device.id),
                    ("command_id", "=", int(command_id)),
                    ("state", "in", ("sent", "done")),
                ], limit=1)
                if cmd and cmd.state == "sent" and str(record.get("return")) == "0":
                    option = None
                    if cmd.command in ("INFO", "GET OPTION FROM FWVersion", "GET OPTION FROM PushVersion"):
                        if cmd.command.startswith("GET OPTION FROM "):
                            option = cmd.command[len("GET OPTION FROM "):]
                        # Includes multiline INFO and Content=... values.
                        # INFO replies often put IDs and version fields on
                        # separate lines. Only combine those lines when the
                        # payload refers to exactly one command ID.
                        reply_text = (raw if len(reply_ids) == 1 else
                            "&".join("%s=%s" % (k, v) for k, v in record.items()))
                        versions = extract_versions(reply_text, option_key=option)
                        self._save_version_info(device, versions, "DEVICECMD %s" % cmd.command[:40], cmd)
                device.acknowledge_adms_command(command_id, record.get("return"))
        return self._resp("OK")

    # ----------------------------
    # Payload parsing
    # ----------------------------
    def _iter_attendance_records(self, table, raw):
        """Yield normalized punch dictionaries from ATTLOG or Security PUSH RTLOG."""
        for original_line in raw.splitlines():
            line = (original_line or "").strip()
            if not line:
                continue

            if table == "RTLOG":
                data = self._parse_kv_line(line, separators=("\t",))
                device_id = data.get("pin")
                dt_str = data.get("time") or data.get("datetime")
                event = data.get("event") or data.get("eventtype")

                # Security PUSH error/alarm/door-state events are not attendance.
                # Keep successful/person-related verification events only.
                if event and event not in self.RTLOG_ATTENDANCE_EVENTS:
                    continue
                if not device_id or device_id in {"0", "-1"} or not dt_str:
                    continue

                punch = data.get("inoutstatus") or data.get("inoutstate") or "0"
                verify = data.get("verifytype") or data.get("verified") or "0"
                yield {
                    "device_id": str(device_id).strip(),
                    "datetime": str(dt_str).strip(),
                    "punch": str(punch).strip(),
                    "verify": str(verify).strip(),
                    "raw": line,
                }
                continue

            # Classic positional ATTLOG.
            cols = line.split("\t")
            if len(cols) >= 2 and "=" not in cols[0]:
                yield {
                    "device_id": str(cols[0]).strip(),
                    "datetime": str(cols[1]).strip(),
                    "punch": str(cols[2]).strip() if len(cols) > 2 and str(cols[2]).strip() else "0",
                    "verify": str(cols[3]).strip() if len(cols) > 3 and str(cols[3]).strip() else "0",
                    "raw": line,
                }
                continue

            # Some newer attendance firmware sends key=value ATTLOG rows.
            data = self._parse_kv_line(line, separators=("\t",))
            device_id = data.get("pin") or data.get("userid") or data.get("user_id")
            dt_str = data.get("datetime") or data.get("time")
            if device_id and dt_str:
                yield {
                    "device_id": str(device_id).strip(),
                    "datetime": str(dt_str).strip(),
                    "punch": str(data.get("status") or data.get("punch") or "0").strip(),
                    "verify": str(data.get("verified") or data.get("verifytype") or data.get("verifymode") or "0").strip(),
                    "raw": line,
                }

    # ----------------------------
    # DB save helper
    # ----------------------------
    def _store_attendance_payload(self, device, raw, table="ATTLOG"):
        """Store punches idempotently in the current HTTP transaction.

        Do not open a second registry cursor and do not commit manually here.
        Odoo owns the request transaction and may retry it on serialization
        failures. New events receive a nullable source fingerprint, so duplicate
        protection is concurrency-safe without rewriting or deleting historical
        attendance rows. Savepoints keep one duplicate collision from aborting
        the whole device batch.
        """
        sn = (device.serial_number or device.name) if device else ""
        if not device or not device.exists():
            raise ValueError("Unknown ZK device")

        if not device.allow_push:
            _logger.warning("ZK Device %s is blocked (allow_push=False). Push rejected.", sn)
            return 0, 0, 0

        env = request.env
        ZkLog = env["zk.machine.attendance"].sudo()
        HrAttendance = env["hr.attendance"].sudo()

        created = 0
        skipped = 0
        unmapped = 0

        try:
            device_tz = pytz.timezone(device.tz or "UTC")
        except Exception:
            _logger.warning("ZK Device %s has invalid timezone %r; using UTC.", sn, device.tz)
            device_tz = pytz.UTC

        touched_days = set()
        # Device/PIN mapping is authoritative. It permits the same PIN on
        # different legacy terminals without mapping one person to another.
        DeviceUser = env["zk.device.user"].sudo()
        device_user_map = {
            str(user.pin).strip(): user.employee_id
            for user in DeviceUser.search([("device_id", "=", device.id)]) if user.employee_id
        }



        parsed_any = False
        for record in self._iter_attendance_records(table, raw):
            parsed_any = True
            device_id_num = record["device_id"]
            dt_str = record["datetime"]
            punch = record["punch"] if record["punch"] in self.KNOWN_PUNCH_TYPES else "0"
            verify = record["verify"] if record["verify"] in self.KNOWN_VERIFY_TYPES else False

            try:
                naive_dt = fields.Datetime.to_datetime(dt_str)
                local_dt = device_tz.localize(naive_dt, is_dst=None)
                utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                punch_time_utc = fields.Datetime.to_string(utc_dt)
            except Exception:
                _logger.warning("ZK bad datetime (SN=%s table=%s) line=%r", sn, table, record["raw"])
                skipped += 1
                continue

            emp = device_user_map.get(device_id_num)
            if not emp:
                unmapped += 1
                _logger.debug(
                    "ZK unmapped biometric ID: SN=%s device_user_id=%s. "
                    "Raw punch will be kept without creating an employee.",
                    sn, device_id_num,
                )

            source_event_key = ZkLog._make_source_event_key(
                device.id,
                device_id_num,
                punch_time_utc,
                punch,
            )
            vals = {
                "employee_id": emp.id if emp else False,
                "device_id_num": device_id_num,
                "attendance_type": verify,
                "punch_type": punch,
                "punching_time": punch_time_utc,
                "device_id": device.id,
                "source_event_key": source_event_key,
            }

            # Repeat imports must not duplicate historical or newly keyed raw
            # events. A matching unmapped row may gain its newly verified
            # employee mapping; never rewrite an already mapped raw row.
            _punch, is_new, enriched = ZkLog._zk_upsert_received_punch(vals)
            if is_new:
                created += 1
            else:
                skipped += 1
                if enriched:
                    _logger.info(
                        "ZK existing raw punch enriched (SN=%s PIN=%s UTC=%s)",
                        sn, device_id_num, punch_time_utc,
                    )

            # A retransmitted old event can have a historical employee mapping
            # different from the mapping currently assigned to this device/PIN.
            # Always reconcile the stored event's employee, never today's PIN map.
            actual_employee = _punch.employee_id
            if actual_employee:
                utc_dt_obj = fields.Datetime.from_string(punch_time_utc)
                employee_workday = actual_employee._zk_workday_date(utc_dt_obj)
                touched_days.add((actual_employee.id, employee_workday))

        if table == "RTLOG" and raw.strip():
            # Event 23 is a non-attendance access denial; do not generate a
            # punch. Show limited diagnostics without logging names, PINs,
            # passwords, biometric templates, or entire device RTLOG rows.
            denied = []
            for line in raw.splitlines():
                event = self._parse_kv_line(line, separators=("\t",))
                if event.get("event") in ("22", "23"):
                    denied.append(event)
            if denied:
                _logger.info(
                    "ZK RTLOG access rejection diagnostics: SN=%s event_22=%s event_23=%s",
                    sn,
                    sum(row.get("event") == "22" for row in denied),
                    sum(row.get("event") == "23" for row in denied),
                )
                # Only a recent event is useful for detecting a terminal
                # clock ahead/behind UTC by roughly an hour; an old buffered
                # event would otherwise produce a false skew alert.
                reported = denied[-1].get("time")
                try:
                    local_clock = device_tz.localize(fields.Datetime.to_datetime(reported))
                    skew = (local_clock.astimezone(pytz.UTC).replace(tzinfo=None)
                            - datetime.datetime.utcnow()).total_seconds()
                    if 300 < abs(skew) < 4 * 3600:
                        _logger.warning(
                            "ZK possible terminal clock/timezone mismatch: SN=%s "
                            "configured_tz=%s reported_utc_skew_minutes=%s",
                            sn, device.tz, round(skew / 60),
                        )
                except (TypeError, ValueError, pytz.AmbiguousTimeError,
                        pytz.NonExistentTimeError):
                    pass
        if raw.strip() and not parsed_any and table != "RTLOG":
            _logger.warning(
                "ZK %s payload had no supported attendance rows (SN=%s bytes=%s)",
                table, sn, len(raw),
            )

        # hr.attendance is best-effort, but remains in the same request transaction.
        # A savepoint protects raw logs from HR-side business-rule failures without
        # creating an independent commit that can conflict with the HTTP transaction.
        # A device can send multiple days in one unordered batch. Process local
        # dates chronologically so the next day's check-in closes an older open
        # biometric attendance BEFORE Odoo validates the new check-in.
        for emp_id, work_date in sorted(touched_days):
            try:
                with env.cr.savepoint():
                    outcome = HrAttendance._zk_sync_employee_day(
                        emp_id, work_date, finalize_missing=True,
                    )
                    if outcome == "conflict":
                        _logger.debug(
                            "ZK raw punches retained; HR workday conflict preserved "
                            "(SN=%s employee_id=%s date=%s)", sn, emp_id, work_date,
                        )
            except ValidationError as exc:
                _logger.warning(
                    "ZK HR reconciliation requires manual review; raw punches "
                    "retained (SN=%s employee_id=%s date=%s): %s",
                    sn, emp_id, work_date, exc,
                )
            except Exception:
                _logger.exception(
                    "ZK HR attendance sync skipped but raw ZK logs kept "
                    "in the request transaction (SN=%s employee_id=%s work_date=%s)",
                    sn, emp_id, work_date,
                )

        return created, skipped, unmapped
