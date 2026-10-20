from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    user_customer_domain = fields.Binary(
        string="User Customer Domain",
        compute="_compute_user_customer_domain",
    )
    department_partner_domain = fields.Binary(
        string="Department Partner Domain (Legacy)",
        compute="_compute_user_customer_domain",
        help=(
            "Legacy compatibility field retained for previously installed "
            "Sale Order views. Customer filtering is now based on industries "
            "configured on the current user."
        ),
    )

    def _get_allowed_customer_industries(self):
        return self.env.user.sale_customer_industry_ids

    @api.depends("company_id", "partner_id")
    @api.depends_context("uid", "company", "allowed_company_ids")
    def _compute_user_customer_domain(self):
        allowed_industries = self._get_allowed_customer_industries()

        for order in self:
            company = order.company_id or self.env.company
            domain = [
                ("customer_rank", ">", 0),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]

            if allowed_industries:
                domain.append(
                    ("industry_id", "in", allowed_industries.ids)
                )

            # Keep an already selected customer visible while editing an
            # existing order, but validation still prevents saving an
            # unauthorized customer.
            if order.partner_id:
                domain = ["|", ("id", "=", order.partner_id.id)] + domain

            order.user_customer_domain = domain
            order.department_partner_domain = domain

    def _validate_partner_allowed_for_user(self):
        allowed_industries = self._get_allowed_customer_industries()
        if not allowed_industries:
            return

        allowed_industry_ids = set(allowed_industries.ids)
        for order in self:
            if not order.partner_id:
                continue

            partner_industry_id = order.partner_id.industry_id.id
            if partner_industry_id not in allowed_industry_ids:
                raise ValidationError(
                    _(
                        "Customer '%(customer)s' is not allowed for user "
                        "'%(user)s'. Select a customer whose Industry is one "
                        "of the user's configured Customer Industries."
                    )
                    % {
                        "customer": order.partner_id.display_name,
                        "user": self.env.user.display_name,
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._validate_partner_allowed_for_user()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if "partner_id" in vals or "company_id" in vals:
            self._validate_partner_allowed_for_user()
        return result

    def action_confirm(self):
        self._validate_partner_allowed_for_user()
        return super().action_confirm()
