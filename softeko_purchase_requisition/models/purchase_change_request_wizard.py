# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class PurchaseRequisitionChangeRequestWizard(models.TransientModel):
    _name = "softeko.purchase.requisition.change.request.wizard"
    _description = "Purchase Requisition Reset / Cancel Request"

    requisition_id = fields.Many2one(
        "softeko.purchase.requisition", required=True, readonly=True, ondelete="cascade"
    )
    action_type = fields.Selection(
        [("reset", "Reset to Draft"), ("cancel", "Cancel Requisition")],
        required=True,
        readonly=True,
    )
    # Keep this field non-required at ORM level and validate in action_confirm().
    # In Odoo 19, an object button on a new TransientModel with a missing required
    # field can reach the method with an empty recordset, causing ensure_one() to
    # raise an RPC traceback instead of a user-friendly validation message.
    reason = fields.Text()

    def action_confirm(self):
        if not self:
            raise UserError(_("Please enter a reason before confirming."))
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(_("Please enter a reason before confirming."))
        if self.action_type == "reset":
            return self.requisition_id.action_request_reset(self.reason.strip())
        return self.requisition_id.action_request_cancel(self.reason.strip())
