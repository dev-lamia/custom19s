from odoo import models

class CrmLead2OpportunityPartner(models.TransientModel):
    _inherit = "crm.lead2opportunity.partner"

    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        lead_id = vals.get("lead_id")
        if not lead_id:
            return vals

        lead = self.env["crm.lead"].browse(lead_id)

        if not lead.partner_name:
            return vals

        # 1. Check existing opportunities/leads
        duplicate_leads = self.env["crm.lead"].search([
            ("id", "!=", lead.id),
            ("partner_name", "=ilike", lead.partner_name),
        ])

        if duplicate_leads:
            vals.update({
                "name": "merge",
                "duplicated_lead_ids": [
                    (6, 0, duplicate_leads.ids)
                ],
            })
            return vals

        # 2. Check existing customers/contacts
        partner = self.env["res.partner"].search([
            ("name", "=ilike", lead.partner_name),
        ], limit=1)

        if partner:
            vals.update({
                "action": "exist",
                "partner_id": partner.id,
            })

        return vals

    