# -*- coding: utf-8 -*-
"""Pure parsing helpers for Security PUSH tabledata, without Odoo dependencies.

Never include raw records or template bytes in exception/log messages.
"""
import base64
import binascii
import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_TEMPLATE_BYTES = 2 * 1024 * 1024
# USERPIC is a profile *photograph*, not a BIODATA/BIOPHOTO template.
# The Security PUSH photo-upload protocol expects the literal userpic=<count>
# response after successful persistence. Never advertise BIOPHOTO support.
MAX_USERPIC_BYTES = 2 * 1024 * 1024  # decoded, per photo
MAX_USERPIC_PIXELS = 8 * 1024 * 1024
SUPPORTED_TABLES = frozenset({"user", "biodata", "userpic"})


def server_biometric_support(registry_payload):
    """Security PUSH hybrid-identification handshake masks (types 0..10).

    Advertise only data types we actually parse, persist and can send using
    the unified BIODATA protocol: fingerprint (1) and visible face (9).
    We do not handle the distinct BIOPHOTO table, so advertise no photo types.
    A missing/malformed device capability mask fails closed; never claim an
    unsupported biometric type to firmware.
    """
    registry = {}
    for token in re.split(r"[,\r\n]", registry_payload or ""):
        if "=" in token:
            name, value = token.split("=", 1)
            registry[name.strip().lstrip("~").lower()] = value.strip()

    device_mask = registry.get("multibiodatasupport", "").split(":")
    data_mask = ["0"] * 11
    if len(device_mask) >= 11 and all(bit in ("0", "1") for bit in device_mask[:11]):
        for bio_type in (1, 9):
            if device_mask[bio_type] == "1":
                data_mask[bio_type] = "1"
    photo_mask = ["0"] * 11
    return ":".join(data_mask), ":".join(photo_mask)


def parse_tabledata(raw, table):
    """Return case-normalized rows for a supported table, never log the body."""
    if table not in SUPPORTED_TABLES:
        raise ValueError("Unsupported Security PUSH table")
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("Security PUSH package is too large")
    result = []
    # Some terminals wrap the base64 Content across lines or place Content on
    # the next line. Only USERPIC allows this continuation; never relax
    # BIODATA parsing or confuse a new photo with another user's photo.
    if table == "userpic":
        lines = _userpic_lines(raw)
    else:
        lines = raw.splitlines()
    for original in lines:
        line = original.strip("\x00\r\n ")
        if not line:
            continue
        prefix, sep, remainder = line.partition(" ")
        if sep and prefix.lower() == table:
            line = remainder.strip()
        elif not sep and line.lower() == table:
            continue
        # Firmware uses tab-separated key=value pairs, with a few revisions
        # sending multiple attributes separated by spaces instead.
        parts = re.split(r"\t+|\s+(?=[A-Za-z][A-Za-z0-9_]*=)", line)
        values = {}
        for part in parts:
            if "=" not in part:
                raise ValueError("Invalid Security PUSH table row")
            key, val = part.split("=", 1)
            key = key.strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ValueError("Invalid Security PUSH field name")
            if key in values:
                raise ValueError("Duplicate Security PUSH field name")
            values[key] = val.strip()
        if not values.get("pin"):
            raise ValueError("Security PUSH record is missing PIN")
        result.append(values)
    return result


def decode_biodata_record(values):
    """Validate a device-supplied base64 biometric record for private storage.

    Only cache biometrics; template data must not be pushed between protocol
    families without independent format compatibility verification.
    """
    kind = {"1": "fingerprint", "2": "face", "8": "palm", "9": "face"}.get(
        str(values.get("type", ""))
    )
    if not kind:
        raise ValueError("Unsupported biometric type")
    encoded = values.get("tmp") or ""
    if not encoded or len(encoded) > MAX_TEMPLATE_BYTES * 2:
        raise ValueError("Missing or oversized biometric payload")
    try:
        binary = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid biometric encoding") from exc
    if not binary or len(binary) > MAX_TEMPLATE_BYTES:
        raise ValueError("Invalid biometric payload size")
    slot = values.get("no", values.get("index", "0"))
    try:
        slot = int(slot)
        valid = int(values.get("valid", "1"))
        no = int(values.get("no", "0"))
        index = int(values.get("index", "0"))
        fmt = int(values.get("format", "0"))
        duress = int(values.get("duress", "0"))
        exact_type = int(values["type"])
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid biometric metadata") from exc
    if not (0 <= slot <= 65535 and 0 <= no <= 99 and 0 <= index <= 655):
        raise ValueError("Invalid biometric template slot")
    version = "%s.%s" % (values.get("majorver") or "", values.get("minorver") or "")
    if version == ".":
        version = False
    if values.get("format") not in (None, ""):
        version = "%s;format=%s" % (version or "unknown", values["format"])
    return {
        "pin": values["pin"],
        "biometric_type": kind,
        # Retain previous IDs for index=0; permit additional templates for
        # the same finger without silently overwriting cached index=0 data.
        "template_index": no + index * 100,
        "security_no": no,
        "security_index": index,
        "security_format": fmt,
        "security_duress": duress,
        "security_type": exact_type,
        "security_metadata_complete": all(k in values for k in (
            "no", "index", "format", "duress", "majorver", "minorver", "type"
        )),
        "template_version": version,
        "valid": valid,
        "template_size": len(binary),
        # ORM fields.Binary stores base64 bytes/string, not decoded bytes.
        "template": encoded,
    }


def _userpic_lines(raw):
    """Group one USERPIC record, allowing base64 continuation line wrapping.

    Do not concatenate unrecognized input: rejecting malformed packets
    prevents accidentally attaching another person's picture to a PIN.
    """
    records = []
    current = ""
    for original in raw.splitlines():
        line = original.strip("\x00\r\n ")
        if not line:
            continue
        beginning = bool(re.match(r"(?i)^(?:userpic\s+)?pin=", line))
        if beginning:
            if current:
                records.append(current)
            current = line
        elif current and re.match(r"(?i)^content=", line) and not re.search(
            r"(?i)(?:^|\s)content=", current
        ):
            current += "\t" + line
        elif current and re.search(r"(?i)(?:^|\s)content=", current) and re.fullmatch(
            r"[A-Za-z0-9+/=]+", line
        ):
            current += line
        else:
            raise ValueError("Invalid Security PUSH user photo record")
    if current:
        records.append(current)
    return records


def decode_userpic_record(values):
    """Validate a profile JPG and strip metadata before placing it in Odoo.

    Do not log encoded photo data, arbitrary filenames or rejected payloads.
    Re-encoding removes EXIF/geotags and ensures a JPEG which Odoo can render.
    """
    pin = (values.get("pin") or "").strip()
    if not re.fullmatch(r"[0-9]{1,12}", pin):
        raise ValueError("Invalid Security PUSH photo PIN")
    filename = (values.get("filename") or "").strip()
    if not filename or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", filename) or not filename.lower().endswith((".jpg", ".jpeg")):
        raise ValueError("Invalid Security PUSH photo filename")
    encoded = (values.get("content") or "").strip()
    try:
        encoded_size = int(values.get("size", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Security PUSH photo size") from exc
    if (not encoded or encoded_size != len(encoded) or
            encoded_size > ((MAX_USERPIC_BYTES + 2) // 3) * 4 or
            encoded_size <= 0):
        raise ValueError("Security PUSH photo size mismatch")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid Security PUSH photo encoding") from exc
    if not decoded or len(decoded) > MAX_USERPIC_BYTES or not decoded.startswith(b"\xff\xd8\xff"):
        raise ValueError("Unsupported Security PUSH photo content")
    try:
        with Image.open(io.BytesIO(decoded)) as img:
            if img.format != "JPEG" or img.width <= 0 or img.height <= 0 or img.width * img.height > MAX_USERPIC_PIXELS:
                raise ValueError("Unsupported Security PUSH photo dimensions")
            # Decode the complete JPEG rather than trusting its header.
            img.load()
            normalized = ImageOps.exif_transpose(img).convert("RGB")
            out = io.BytesIO()
            normalized.save(out, format="JPEG", quality=85, optimize=True)
            sanitized = out.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("Corrupt or unsupported Security PUSH photo") from exc
    if len(sanitized) > MAX_USERPIC_BYTES:
        raise ValueError("Security PUSH photo exceeds storage limit")
    return {"pin": pin, "image_1920": base64.b64encode(sanitized).decode("ascii")}
