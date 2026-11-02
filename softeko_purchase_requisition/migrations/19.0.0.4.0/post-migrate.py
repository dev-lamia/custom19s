# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Remove obsolete allocation-review activities left by the old quantity-allocation engine.
    obsolete = env["mail.activity"].sudo().search([
        ("res_model", "=", "softeko.purchase.requisition"),
        ("summary", "ilike", "Review split RFQ allocation"),
    ])
    obsolete.unlink()

    # Re-evaluate only document-level completion after dropping quantity reconciliation.
    requisitions = env["softeko.purchase.requisition"].with_context(active_test=False).search([
        ("state", "in", ["po_issued", "done"]),
    ])
    requisitions._recompute_procurement_state()
