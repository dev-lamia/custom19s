# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleSupplierDocument(models.Model):
    _name = "sale.supplier.document"
    _description = "Supplier Document on Sale Order"
    _order = "sequence, id desc"

    name = fields.Char(string="Description")
    sequence = fields.Integer(default=10)

    type_id = fields.Many2one(
        comodel_name="supplier.document.type",
        string="Type",
        required=True,
        domain="[('sale_ok', '=', True), ('active', '=', True)]",
    )

    file = fields.Binary(string="File")
    file_filename = fields.Char(string="Filename")

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        ondelete="cascade",
    )

    purchase_document_id = fields.Many2one(
        comodel_name="purchase.supplier.document",
        string="Source Purchase Document",
    )

    source_po_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Source PO",
    )



class SaleOrder(models.Model):
    _inherit = "sale.order"

    supplier_po_ids = fields.Many2many(
        comodel_name="purchase.order",
        relation="sale_supplier_purchase_rel",
        column1="sale_id",
        column2="purchase_id",
        string="Related Purchase Orders",
        help="Select one or more Purchase Orders to copy their Supplier Documents.",
    )

    supplier_document_ids = fields.One2many(
        comodel_name="sale.supplier.document",
        inverse_name="order_id",
        string="Supplier Documents",
    )

    @api.onchange("supplier_po_ids")
    def _onchange_supplier_po_ids(self):
        """Rebuild PO-based Supplier Documents, keep manual ones, no duplicates."""
        for order in self:
            commands = []

            # 1) Keep existing MANUAL lines: those without source_po_id
            manual_vals_list = []
            for line in order.supplier_document_ids:
                if not line.source_po_id:
                    manual_vals_list.append({
                        "sequence": line.sequence,
                        "type_id": line.type_id.id,
                        "name": line.name,
                        "file": line.file,
                        "file_filename": line.file_filename,
                        # no purchase_document_id / source_po_id => manual
                    })

            # 2) Clear all existing lines
            commands.append((5, 0, 0))

            # 3) Recreate manual lines
            for vals in manual_vals_list:
                commands.append((0, 0, vals))

            # 4) Add lines from currently selected POs (no duplicates)
            seen = set()
            for po in order.supplier_po_ids:
                for doc in po.supplier_document_ids:
                    key = (po.id, doc.id)
                    if key in seen:
                        continue
                    seen.add(key)

                    commands.append(
                        (0, 0, {
                            "sequence": doc.sequence,
                            "type_id": doc.type_id.id,
                            "name": doc.name,
                            "file": doc.file,
                            "file_filename": doc.file_filename,
                            "purchase_document_id": doc.id,
                            "source_po_id": po.id,
                        })
                    )

            # 5) Apply all at once
            order.supplier_document_ids = commands
