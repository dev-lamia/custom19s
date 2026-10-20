from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = "res.users"

    sale_customer_industry_ids = fields.Many2many(
        comodel_name="res.partner.industry",
        relation="res_users_sale_customer_industry_rel",
        column1="user_id",
        column2="industry_id",
        string="Customer Industries",
        help=(
            "When industries are selected, the Customer field on Sale Orders "
            "only shows customers whose Industry matches one of these values. "
            "Leave empty to allow all customers."
        ),
    )

    # Legacy compatibility field retained so existing databases/upgrades that
    # still reference the old field do not fail. It is no longer used for
    # Sale Order customer filtering.
    sale_customer_tag_ids = fields.Many2many(
        comodel_name="res.partner.category",
        relation="res_users_sale_customer_tag_rel",
        column1="user_id",
        column2="category_id",
        string="Customer Tags (Legacy)",
        help="Legacy field. Sale Order customer filtering now uses Industry.",
    )

    @api.model
    def _get_sale_customer_industries(self):
        return self.env.user.sale_customer_industry_ids
