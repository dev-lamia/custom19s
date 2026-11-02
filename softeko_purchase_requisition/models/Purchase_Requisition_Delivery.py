from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequisitionDelivery(models.Model):
    _name = "softeko.purchase.requisition.delivery"
    _description = "Purchase Requisition Delivery Schedule"

    line_id = fields.Many2one(
        "softeko.purchase.requisition.line",
        string="Requisition Line",
        required=True,
        ondelete="cascade",
    )

    categ_id = fields.Many2one(
        "product.category",
        string="Category",
        related="line_id.categ_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="line_id.product_id",
        store=True,
        readonly=True,
    )
    total_quantity = fields.Float(
        string="Total Quantity",
        related="line_id.product_qty",
        store=True,
        readonly=True,
    )

    delivery_location = fields.Char(string="Delivery Location")
    remark = fields.Text(string="Remark")

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "purchase_requisition_delivery_attachment_rel",
        "delivery_id",
        "attachment_id",
        string="Attachments",
    )

    schedule_line_ids = fields.One2many(
        "softeko.purchase.requisition.delivery.line",
        "delivery_id",
        string="Delivery Lines",
    )

    @api.constrains("schedule_line_ids")
    def _check_schedule_total(self):
        for rec in self:
            # If there are no lines yet, don't block the user from opening/saving
            if not rec.schedule_line_ids:
                continue

            total_lines = sum(rec.schedule_line_ids.mapped("quantity") or [0.0])
            total_qty = rec.total_quantity or 0.0

            # Allow a small rounding tolerance
            if abs(total_lines - total_qty) > 1e-6:
                raise ValidationError(
                    _(
                        "The sum of all delivery line quantities (%.2f) "
                        "must equal the total quantity (%.2f)."
                    )
                    % (total_lines, total_qty)
                )