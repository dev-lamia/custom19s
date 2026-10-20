import re
from datetime import date, datetime

from odoo import fields, _


PLACEHOLDER_VALUES = {False, "", "/", "New", _("New")}
STANDARD_SEQUENCE_TOKENS = {
    "year", "month", "day", "y", "doy", "woy", "weekday",
    "h24", "h12", "min", "sec", "isoyear", "isoy", "isoweek",
}
TOKEN_PATTERN = re.compile(r"%\(([^)]+)\)s")


def get_company(recordset, vals=None):
    vals = vals or {}
    if "company_id" in recordset._fields:
        company_id = vals.get("company_id")
        if company_id:
            company = recordset.env["res.company"].browse(company_id).exists()
            if company:
                return company
        if recordset and len(recordset) == 1 and recordset.company_id:
            return recordset.company_id
    return recordset.env.company


def get_sequence_date(recordset, vals=None):
    vals = vals or {}
    for field_name in ("date", "date_order", "invoice_date", "scheduled_date"):
        if field_name not in recordset._fields:
            continue
        value = vals.get(field_name)
        if value is None and recordset and len(recordset) == 1:
            value = recordset[field_name]
        if not value:
            continue
        field = recordset._fields[field_name]
        if isinstance(value, str):
            value = (
                fields.Datetime.to_datetime(value)
                if field.type == "datetime"
                else fields.Date.to_date(value)
            )
        if isinstance(value, (date, datetime)):
            return value
    return None


def has_supported_name_field(recordset):
    """Return whether the business model has a writable Char/Text `name` field."""
    if "name" not in recordset._fields:
        return False
    field = recordset._fields["name"]
    if field.type not in ("char", "text"):
        return False
    if field.compute and not field.inverse:
        return False
    return True


def _is_standard_token(token):
    if token in STANDARD_SEQUENCE_TOKENS:
        return True
    for prefix in ("range_", "current_"):
        if token.startswith(prefix) and token[len(prefix):] in STANDARD_SEQUENCE_TOKENS:
            return True
    return False


def get_dynamic_token_paths(sequence):
    """Return non-date token paths used by prefix/suffix."""
    tokens = set()
    for template in (sequence.prefix or "", sequence.suffix or ""):
        tokens.update(TOKEN_PATTERN.findall(template))
    return sorted(token for token in tokens if not _is_standard_token(token))


def _stringify_token_value(value):
    if value is False or value is None:
        return ""
    if hasattr(value, "_name"):
        if not value:
            return ""
        if len(value) == 1:
            return value.display_name or ""
        return ",".join(value.mapped("display_name"))
    if isinstance(value, (date, datetime)):
        return fields.Datetime.to_string(value) if isinstance(value, datetime) else fields.Date.to_string(value)
    return str(value)


def resolve_record_field_path(record, field_path):
    """Resolve a dotted model field path on a real or `new()` record."""
    current = record
    parts = field_path.split(".")
    for index, part in enumerate(parts):
        if not hasattr(current, "_fields") or part not in current._fields:
            return ""
        current = current[part]
        if current in (False, None):
            return ""
        if index < len(parts) - 1 and not hasattr(current, "_fields"):
            return ""
    return _stringify_token_value(current)


def get_dynamic_sequence_values(sequence, record):
    return {
        path: resolve_record_field_path(record, path)
        for path in get_dynamic_token_paths(sequence)
    }


def get_next_sequence_value(sequence, record, sequence_date=None):
    """Generate a sequence value and apply the configured independent counter."""
    dynamic_values = get_dynamic_sequence_values(sequence, record)
    counter_path = sequence._get_counter_field_path()
    counter_key = (
        resolve_record_field_path(record, counter_path) if counter_path else ""
    )
    return sequence.with_context(
        conditional_sequence_values=dynamic_values,
        conditional_sequence_counter_key=counter_key,
    ).next_by_id(sequence_date=sequence_date)


def prepare_conditional_values(recordset, vals_list):
    """Inject a matching conditional number before the business model create()."""
    sequence_model = recordset.env["ir.sequence"]

    for vals in vals_list:
        company = get_company(recordset, vals)
        scoped = recordset.with_company(company)
        sequences = sequence_model.with_company(company)._get_model_sequences(
            recordset._name,
            company,
        )
        if not sequences:
            continue

        preview_vals = dict(vals)
        if "company_id" in recordset._fields and not preview_vals.get("company_id"):
            preview_vals["company_id"] = company.id

        preview = scoped.new(preview_vals)
        sequence = sequence_model.with_company(company)._get_for_record(preview)
        if not sequence or not has_supported_name_field(recordset):
            continue

        field_name = "name"
        if field_name in vals and vals[field_name] not in PLACEHOLDER_VALUES:
            continue

        vals[field_name] = get_next_sequence_value(
            sequence,
            preview,
            sequence_date=get_sequence_date(preview, vals),
        )


def regenerate_after_condition_change(records, changed_values, *, allow=True):
    """Re-evaluate only when a field used by a configured domain changed."""
    if not allow or not records or records.env.context.get("skip_conditional_sequence"):
        return

    sequence_model = records.env["ir.sequence"]
    changed_fields = set(changed_values)

    for record in records:
        company = get_company(record)
        seq_env = sequence_model.with_company(company)
        watched = seq_env._get_watched_fields(record._name, company)
        if not (changed_fields & watched):
            continue

        sequence = seq_env._get_for_record(record)
        if not sequence or not has_supported_name_field(record):
            continue

        generated = get_next_sequence_value(
            sequence,
            record,
            sequence_date=get_sequence_date(record),
        )
        record.with_context(skip_conditional_sequence=True).write({"name": generated})
