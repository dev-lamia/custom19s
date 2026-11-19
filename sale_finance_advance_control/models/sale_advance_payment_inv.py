from odoo import models, _
from odoo.exceptions import AccessError, UserError

from .sale_order import FINANCE_GROUP


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _check_finance_invoice_access(self, orders):
        if not self.env.user.has_group(FINANCE_GROUP):
            raise AccessError(_("Only Finance Approvers may invoice Sales Orders."))
        if any(order.state != "sale" for order in orders):
            raise UserError(_("Confirm the Sales Order before creating an invoice."))

    def create_invoices(self):
        self._check_finance_invoice_access(self.sale_order_ids)
        return super().create_invoices()

    def _create_invoices(self, sale_orders):
        self._check_finance_invoice_access(sale_orders)
        return super()._create_invoices(sale_orders)
