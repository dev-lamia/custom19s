# -*- coding: utf-8 -*-
from odoo import models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def _get_alternative_values(self):
        values = super()._get_alternative_values()
        origin = self.origin_po_id
        if not origin:
            return values
        requisitions = origin._get_linked_requisitions()
        for vals in values:
            if origin.pr_requisition_id:
                vals["pr_requisition_id"] = origin.pr_requisition_id.id
            if requisitions:
                vals["pr_requisition_ids"] = [(6, 0, requisitions.ids)]
        return values
