# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SupplierDocumentType(models.Model):
    _name = "supplier.document.type"
    _description = "Supplier Document Type"
    _order = "sequence, name"

    name = fields.Char(string="Document Type", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    sale_ok = fields.Boolean(
        string="Sales",
        default=True,
        help="If checked, this document type can be used on Sale Orders.",
    )
    purchase_ok = fields.Boolean(
        string="Purchase",
        default=True,
        help="If checked, this document type can be used on Purchase Orders.",
    )

    vendor_ok = fields.Boolean(
    string="Vendor",
    default=False,
    help="If checked, this document type can be used on Vendor (Contact) documents.",
    )

    customer_ok = fields.Boolean(
    string="Customer",
    default=False,
    help="If checked, this document type can be used on Customer documents.",
    )
