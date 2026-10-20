# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class PurchaseSupplierDocument(models.Model):
    _name = "purchase.supplier.document"
    _description = "Supplier Document on Purchase Order"
    _order = "sequence, id desc"

    name = fields.Char(string="Description")
    sequence = fields.Integer(default=10)
    type_id = fields.Many2one(
        comodel_name="supplier.document.type",
        string="Type",
        required=True,
        domain="[('purchase_ok', '=', True), ('active', '=', True)]", 
    )
    file = fields.Binary(string="File")
    file_filename = fields.Char(string="Filename")
    order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        ondelete="cascade",
    )



class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    supplier_document_ids = fields.One2many(
        comodel_name="purchase.supplier.document",
        inverse_name="order_id",
        string="Supplier Documents",
    )

    vendor_expired_document_type_ids = fields.Many2many(
        related="partner_id.expired_vendor_document_type_ids",
        store=False,
    )

    vendor_expired_document_type_names = fields.Char(
        related="partner_id.expired_vendor_document_type_names",
        store=False,
    )

    def button_confirm(self):
        for order in self:
            if order.partner_id.expired_vendor_document_type_ids:
                raise UserError(_(
                    "Vendor: %(vendor)s\n\n"
                    "The following vendor document(s) are expired or expiring within 30 days:\n"
                    "%(docs)s\n\n"
                    "Please update the vendor documents before confirming the Purchase Order."
                ) % {
                    "vendor": order.partner_id.display_name,
                    "docs": order.partner_id.expired_vendor_document_type_names,
                })

        return super().button_confirm()

