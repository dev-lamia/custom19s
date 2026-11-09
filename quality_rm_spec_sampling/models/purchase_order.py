"""No custom PR or TDS-based PO approval restriction.

Purchase orders follow standard Odoo Purchase. Quality is assessed on receipt.
"""
from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
