from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def name_search(
        self,
        name="",
        domain=None,
        operator="ilike",
        limit=100,
    ):
        """Restrict Sale Order customers by the current user's industries."""
        search_domain = list(domain or [])

        if self.env.context.get("filter_sale_customer_by_user_industries"):
            industry_ids = self.env.user.sale_customer_industry_ids.ids
            if industry_ids:
                search_domain.append(("industry_id", "in", industry_ids))

        return super().name_search(
            name=name,
            domain=search_domain,
            operator=operator,
            limit=limit,
        )
