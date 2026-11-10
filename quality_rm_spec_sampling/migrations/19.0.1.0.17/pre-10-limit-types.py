"""Before the ORM loads 19.0.1.0.17: keep existing numeric limits.

limit_mode becomes computed from the new limit_type field. Fill limit_type
first so every previously numeric line stays numeric (as Fixed Min / Max with
its stored LSL/USL) and every reference line stays manual.
"""


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute("""SELECT 1 FROM information_schema.columns
                  WHERE table_name = %s AND column_name = %s""", (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    for table in ('rm_qc_specification_line', 'rm_qc_inspection_parameter'):
        if not _table_exists(cr, table) or not _column_exists(cr, table, 'limit_mode'):
            continue
        cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS limit_type varchar' % table)
        cr.execute("""UPDATE %s SET limit_type = CASE WHEN limit_mode = 'numeric'
                      THEN 'minmax' ELSE 'reference' END
                      WHERE limit_type IS NULL""" % table)

    table = 'rm_qc_specification_line'
    if (_table_exists(cr, table) and _column_exists(cr, table, 'nominal_set')
            and _column_exists(cr, table, 'nominal_numeric')):
        cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS target_numeric numeric' % table)
        cr.execute("""UPDATE %s SET target_numeric = nominal_numeric
                      WHERE nominal_set AND target_numeric IS NULL""" % table)
