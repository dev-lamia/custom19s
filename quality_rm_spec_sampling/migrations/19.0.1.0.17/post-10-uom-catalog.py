"""After upgrade: unit dropdown values, default catalog errors per test and
automatic limit types for DRAFT standards. Active standards and recorded
inspection results are not changed."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['rm.qc.uom']._rm_qc_sync_master_data()
