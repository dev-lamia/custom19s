# -*- coding: utf-8 -*-
from odoo import fields, models


class VendorDocument(models.Model):
    _name = "vendor.document"
    _description = "Vendor Document"
    _order = "sequence, id desc"

    sequence = fields.Integer(default=10)
    type_id = fields.Many2one(
    comodel_name="supplier.document.type",
    string="Type",
    required=True,
    domain="[('vendor_ok', '=', True), ('active', '=', True)]",
    context={
        "default_vendor_ok": True,
        "default_sale_ok": False,
        "default_purchase_ok": False,
    },
    )
    name = fields.Char(string="Description")
    file = fields.Binary(string="File", attachment=True)
    file_filename = fields.Char(string="Filename")
    expiry_date = fields.Date(string="Expiry Date")
    department_id = fields.Many2one("hr.department", string="Notify Department")
    stop_notifications = fields.Boolean(string="Stop Notifications", default=False)
    last_notified_on = fields.Date(string="Last Notified On")

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        required=True,
        ondelete="cascade",
    )
