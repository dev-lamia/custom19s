# -*- coding: utf-8 -*-
"""Non-destructive migration for 19.0.0.0.5.

The 19.0.0.0.4 release added a UNIQUE constraint directly on historical raw
attendance columns.  v0.5 replaces it with a nullable event fingerprint so
existing rows are never modified or deleted during upgrade.
"""
import logging
import re

_logger = logging.getLogger(__name__)


def _normalize_constraint(definition):
    return re.sub(r'\s+', '', (definition or '').replace('"', '').lower())


def migrate(cr, version):
    # Drop only the exact v0.4 four-column UNIQUE constraint if it exists.
    # This changes schema only; it never deletes or updates attendance rows.
    cr.execute(
        """
        SELECT c.conname, pg_get_constraintdef(c.oid)
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
         WHERE t.relname = 'zk_machine_attendance'
           AND c.contype = 'u'
        """
    )
    expected = "unique(device_id,device_id_num,punching_time,punch_type)"
    for constraint_name, definition in cr.fetchall():
        if _normalize_constraint(definition) == expected:
            cr.execute(
                'ALTER TABLE zk_machine_attendance DROP CONSTRAINT IF EXISTS "%s"'
                % constraint_name.replace('"', '""')
            )
            _logger.warning(
                "tam_hr_zk_attendance: dropped legacy v0.4 raw-punch UNIQUE "
                "constraint %s without changing any attendance rows",
                constraint_name,
            )
