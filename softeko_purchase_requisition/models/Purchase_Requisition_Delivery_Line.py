from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequisitionDeliveryLine(models.Model):
    _name = "softeko.purchase.requisition.delivery.line"
    _description = "Purchase Requisition Delivery Schedule Line"
    _order = "schedule_date, id"

    delivery_id = fields.Many2one(
        "softeko.purchase.requisition.delivery",
        string="Delivery Schedule",
        required=True,
        ondelete="cascade",
    )

    schedule_date = fields.Date(string="Month/Date", required=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="UoM")
    remarks = fields.Char(string="Remarks")

    @api.onchange("delivery_id")
    def _onchange_delivery_id(self):
        for line in self:
            if line.delivery_id and line.delivery_id.line_id.product_uom_id:
                line.uom_id = line.delivery_id.line_id.product_uom_id