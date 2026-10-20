"""Ensure WhatsApp columns exist before ORM schema synchronization."""


def migrate(cr, version):
    for table in (
        "res_partner",
        "crm_lead",
        "crm_requirement_form",
    ):
        cr.execute(
            f"""
            ALTER TABLE IF EXISTS {table}
            ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR
            """
        )
