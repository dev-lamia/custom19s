def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
        )
        """,
        (table, column),
    )
    return cr.fetchone()[0]


def migrate(cr, version):
    """Backfill legacy device names only after the new column exists.

    This migration runs after Odoo initializes the module schema. It is safe for
    databases upgraded from versions that never had ``serial_number``.
    """
    if not _column_exists(cr, "zk_device", "serial_number"):
        return

    cr.execute(
        """
        UPDATE zk_device AS device
           SET serial_number = device.name
         WHERE device.serial_number IS NULL
           AND device.name IS NOT NULL
           AND length(device.name) > 0
           AND NOT EXISTS (
               SELECT 1
                 FROM zk_device AS other
                WHERE other.serial_number = device.name
                   OR (other.id != device.id AND other.name = device.name)
           )
        """
    )
