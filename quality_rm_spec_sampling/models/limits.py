"""Pure-Python helpers for QC limit types (no Odoo imports, unit-testable).

Limit types
-----------
pct       Target +/- a percentage chosen from TOLERANCE_PCT
abs       Target +/- a fixed amount
minmax    Fixed minimum and maximum
min       Minimum only (no upper limit, e.g. bond / seal strength)
max       Maximum only
reference Visual / text result judged by the inspector (Pass / Fail)
"""
import re

LIMIT_TYPES = [
    ('pct', '± % of Target'),
    ('abs', '± Fixed amount'),
    ('minmax', 'Fixed Min / Max'),
    ('min', 'Minimum only'),
    ('max', 'Maximum only'),
    ('reference', 'Visual / Manual (Pass-Fail)'),
]
NUMERIC_TYPES = ('pct', 'abs', 'minmax', 'min', 'max')

TOLERANCE_PCT = [
    ('0.5', '0.5%'), ('1', '1%'), ('2', '2%'), ('3', '3%'),
    ('4', '4%'), ('5', '5%'), ('10', '10%'),
]
_PCT_KEYS = {float(key): key for key, _label in TOLERANCE_PCT}

_NUM = re.compile(r'^\s*([+-]?\d+(?:\.\d+)?)\s*%?\s*$')
_REL = re.compile(r'^\s*(?:nominal|standard|target)?\s*([+-])\s*(\d+(?:\.\d+)?)\s*(%)?\s*$', re.I)
_EMPTY = {'', 'n/a', 'na', '-', 'none', 'nil'}


def _plain_number(text):
    """'38' -> 38.0, '95%' -> 95.0; signed relative values ('-5%') excluded."""
    value = (text or '').strip()
    if value[:1] in '+-' and _REL.match(value):
        return None
    match = _NUM.match(value)
    return float(match.group(1)) if match else None


def _relative(text):
    """'Nominal - 5%' / '-5%' / 'Standard + 0.05' -> (sign, amount, is_percent)."""
    value = (text or '').strip()
    if not value or _NUM.match(value) and value[:1] not in '+-':
        return None
    match = _REL.match(value)
    if not match:
        return None
    return match.group(1), float(match.group(2)), bool(match.group(3))


def _is_empty(text):
    return (text or '').strip().lower() in _EMPTY


def guess_limits(lsl_text, target_text, usl_text):
    """Translate workbook LSL/Target/USL text to a limit configuration.

    Returns a dict with limit_type, target_numeric, tolerance_pct,
    tolerance_abs, lsl_numeric and usl_numeric. Anything that is not clearly
    numeric stays 'reference' so nothing is silently misinterpreted.
    """
    result = {'limit_type': 'reference', 'target_numeric': 0.0,
              'tolerance_pct': False, 'tolerance_abs': 0.0,
              'lsl_numeric': 0.0, 'usl_numeric': 0.0}
    target = _plain_number(target_text)
    if target is not None:
        result['target_numeric'] = target

    low_rel, high_rel = _relative(lsl_text), _relative(usl_text)
    if low_rel and high_rel:
        (low_sign, low_amt, low_pct), (high_sign, high_amt, high_pct) = low_rel, high_rel
        if low_sign == '-' and high_sign == '+' and low_amt == high_amt and low_pct == high_pct:
            if low_pct:
                key = _PCT_KEYS.get(low_amt)
                if key:
                    result.update(limit_type='pct', tolerance_pct=key)
            else:
                result.update(limit_type='abs', tolerance_abs=low_amt)
        if result['limit_type'] != 'reference':
            base = result['target_numeric']
            if result['limit_type'] == 'pct':
                delta = abs(base) * float(result['tolerance_pct']) / 100.0
            else:
                delta = result['tolerance_abs']
            result.update(lsl_numeric=round(base - delta, 6),
                          usl_numeric=round(base + delta, 6))
        return result

    low, high = _plain_number(lsl_text), _plain_number(usl_text)
    if low is not None and high is not None and low <= high:
        result.update(limit_type='minmax', lsl_numeric=low, usl_numeric=high)
    elif low is not None and _is_empty(usl_text):
        result.update(limit_type='min', lsl_numeric=low)
    elif high is not None and _is_empty(lsl_text):
        result.update(limit_type='max', usl_numeric=high)
    return result


def compute_limits(limit_type, target, tolerance_pct, tolerance_abs):
    """Return (lsl, usl) for target-based types, else None."""
    target = target or 0.0
    if limit_type == 'pct':
        delta = abs(target) * float(tolerance_pct or 0) / 100.0
    elif limit_type == 'abs':
        delta = abs(tolerance_abs or 0.0)
    else:
        return None
    return round(target - delta, 6), round(target + delta, 6)


def evaluate(limit_type, value, lsl, usl):
    """True = within spec, False = out of spec, None = not numeric type."""
    if limit_type not in NUMERIC_TYPES:
        return None
    if limit_type == 'min':
        return value >= lsl
    if limit_type == 'max':
        return value <= usl
    return lsl <= value <= usl


def format_number(value):
    return ('%.6f' % value).rstrip('0').rstrip('.') if value is not None else ''


def limit_display(limit_type, lsl, usl, unit, lsl_text='', usl_text='', target_text=''):
    unit = (' ' + unit) if unit else ''
    if limit_type in ('minmax', 'pct', 'abs'):
        return '%s – %s%s' % (format_number(lsl), format_number(usl), unit)
    if limit_type == 'min':
        return '≥ %s%s' % (format_number(lsl), unit)
    if limit_type == 'max':
        return '≤ %s%s' % (format_number(usl), unit)
    parts = [p for p in (lsl_text, target_text, usl_text) if p]
    return ('Visual: ' + ' / '.join(parts)) if parts else 'Visual / Manual'
