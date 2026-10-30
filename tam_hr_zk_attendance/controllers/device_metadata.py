# -*- coding: utf-8 -*-
"""Allowlisted, bounded parsing of diagnostic device version fields.

The receiver MUST NOT persist or log arbitrary INFO responses: these can
include credential, network, and other sensitive settings. Parse only the two
requested software identifiers. Pure Python so it can be independently tested.
"""
import re

# Only display-safe release identifiers, not arbitrary device-supplied text.
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()+/\-]{0,95}\Z")
_FIELD = re.compile(
    r"(?:^|[&\r\n\t,]|\bContent=)\s*"
    r"~?(FWVersion|FirmVer|FirmwareVersion|PushVersion)\s*=\s*"
    r"([^&\r\n\t,]{1,120})",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"(?:^|[&\r\n\t])Content=([^&\r\n\t]{1,120})", re.I)
_KEYS = {"fwversion": "firmware_version", "firmver": "firmware_version",
         "firmwareversion": "firmware_version", "pushversion": "push_version"}
_MASK = re.compile(r"[0-9]+(?::[0-9]+){0,31}\Z")


def extract_registry_capabilities(raw):
    """Return a small, display-safe allowlist from a registry payload.

    The registry itself remains private because it may carry credentials and
    network settings. These values are all numeric flags or capability masks.
    """
    if not isinstance(raw, str) or len(raw) > 16384:
        return {}
    registry = {}
    for token in re.split(r"[,\r\n]", raw):
        if "=" in token:
            key, value = token.split("=", 1)
            registry[key.strip().lstrip("~").lower()] = value.strip()
    result = {}
    bool_fields = {"facefunon": "face_function_enabled", "fingerfunon": "finger_function_enabled"}
    int_fields = {
        "maxfingercount": "max_finger_count",
        "maxuserfingercount": "max_user_finger_count",
        "sipdevicetype": "sip_device_type",
    }
    for key, field in bool_fields.items():
        if registry.get(key) in ("0", "1"):
            result[field] = registry[key] == "1"
    for key, field in int_fields.items():
        value = registry.get(key)
        if value and value.isdigit() and 0 <= int(value) <= 1_000_000:
            result[field] = int(value)
    for key, field in {
        "maxmultibiodatacount": "max_multi_biodata_count",
        "maxmultibiophotocount": "max_multi_biophoto_count",
        "multibiodatasupport": "multi_biodata_support",
        "multibiophotosupport": "multi_biophoto_support",
        "multibioversion": "multi_bio_version",
        "zkfpversion": "zkfp_version",
    }.items():
        value = registry.get(key)
        if value and _MASK.fullmatch(value):
            result[field] = value[:255]
    return result


def safe_version(value):
    """Accept a plausible, non-secret human-readable release identifier."""
    value = (value or "").strip().strip('"').strip("'").strip()
    if (not _VERSION.fullmatch(value) or not any(ch.isdigit() for ch in value)
            or value.lower() in {"ok", "null", "false", "none", "0", "1"}
            or value.lower().startswith(("error", "invalid", "unsupported", "unknown"))):
        return None
    return value


def extract_versions(raw, option_key=None):
    """Return only validated FWVersion and PushVersion, never the raw body.

    GET OPTION replies may carry `Content=FWVersion=X` or `Content=X`.
    The latter is only attributed to a known command option key.
    """
    if not isinstance(raw, str) or len(raw) > 16384:
        return {}
    versions = {}
    for match in _FIELD.finditer(raw):
        name = _KEYS[match.group(1).lower()]
        version = safe_version(match.group(2))
        if version:
            versions[name] = version
    requested = _KEYS.get(str(option_key or "").lower())
    if requested and requested not in versions:
        match = _CONTENT.search(raw)
        if match and "=" not in match.group(1):
            version = safe_version(match.group(1))
            if version:
                versions[requested] = version
    return versions
