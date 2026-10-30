"""Re-label proven classic-handshake versions left in the old Push Version slot.

No attendance, user, command, or biometric records are modified.
The original value is PRESERVED in adms_protocol_version before the legacy
installed-software field is cleared. Only classic `att` simple numeric
handshake-style values are moved (e.g., 2.4.1). Complex version strings,
Security PUSH device records, and uncertain values are untouched.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'zk_device'
           AND column_name IN ('push_version','adms_protocol_version','device_type')
    """)
    if {row[0] for row in cr.fetchall()} != {
        'push_version', 'adms_protocol_version', 'device_type'
    }:
        return
    cr.execute("""
        UPDATE zk_device
           SET adms_protocol_version = push_version,
               push_version = NULL
         WHERE lower(device_type) = 'att'
           AND adms_protocol_version IS NULL
           AND push_version ~ '^[0-9]+([.][0-9]+){1,3}$'
    """)
