def migrate(cr, version):
    """Allow raw biometric punches to exist before an employee is mapped."""
    cr.execute(
        "ALTER TABLE zk_machine_attendance "
        "ALTER COLUMN employee_id DROP NOT NULL"
    )
