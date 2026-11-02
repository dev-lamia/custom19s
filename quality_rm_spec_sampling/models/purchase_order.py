from odoo import models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        Spec = self.env['rm.qc.specification']
        for order in self:
            for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id.rm_qc_required):
                if not Spec.with_company(order.company_id)._find_approved(line.product_id):
                    raise UserError(_('Cannot confirm PO %s: %s has no QC Manager-confirmed '
                                      'Incoming RM Specification.')
                                    % (order.name, line.product_id.display_name))
        return super().button_confirm()
