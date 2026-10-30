"""Link historical raw punches to Device Users for grouping only.

Never touch employee mappings, punch values, or derived hr.attendance.
An exact (device_id, PIN) match is mandatory. Unmatched PINs stay NULL.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'zk_machine_attendance'
              AND column_name = 'device_user_id'
        )
    """)
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        UPDATE zk_machine_attendance AS raw
           SET device_user_id = usr.id
          FROM zk_device_user AS usr
         WHERE raw.device_id = usr.device_id
           AND raw.device_id_num = usr.pin
           AND raw.device_user_id IS DISTINCT FROM usr.id
    """)
