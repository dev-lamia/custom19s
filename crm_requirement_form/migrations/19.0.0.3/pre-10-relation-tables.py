"""Repair missing multi-source Many2many tables before loading module models.

Upgrade-time, idempotent schema setup. No existing records are rewritten.
New installations use Odoo's standard Many2many field schema initialization.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Ensure both stored relation tables exist before ORM/view loading."""
    cr.execute("""
        CREATE TABLE IF NOT EXISTS crm_req_form_previous_source_rel (
            form_id INTEGER NOT NULL,
            source_form_id INTEGER NOT NULL,
            PRIMARY KEY (form_id, source_form_id)
        )
    """)
    cr.execute("""
        CREATE INDEX IF NOT EXISTS crm_req_form_previous_source_rel_source_idx
        ON crm_req_form_previous_source_rel (source_form_id, form_id)
    """)
    cr.execute("""
        CREATE TABLE IF NOT EXISTS crm_req_form_loaded_source_rel (
            form_id INTEGER NOT NULL,
            source_form_id INTEGER NOT NULL,
            PRIMARY KEY (form_id, source_form_id)
        )
    """)
    cr.execute("""
        CREATE INDEX IF NOT EXISTS crm_req_form_loaded_source_rel_source_idx
        ON crm_req_form_loaded_source_rel (source_form_id, form_id)
    """)
    _logger.info(
        "CRM Requirement Form %s: ensured multi-source relation tables exist",
        version,
    )
