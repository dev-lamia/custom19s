"""Prepare WhatsApp columns before the module registry reads the new fields.

This migration is intentionally idempotent.  It repairs databases where the
Python field definitions were deployed before the module schema was upgraded.
"""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE IF EXISTS res_partner
        ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR
        """
    )
    cr.execute(
        """
        ALTER TABLE IF EXISTS crm_lead
        ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR
        """
    )
    cr.execute(
        """
        ALTER TABLE IF EXISTS crm_requirement_form
        ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR
        """
    )
