# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


RFQ_STATES = ("draft", "sent", "to approve")


class PurchaseRequisition(models.Model):
    _inherit = "softeko.purchase.requisition"

    def action_open_attach_existing_rfq(self):
        self.ensure_one()
        if self.state != "rfq":
            raise UserError(_("An existing RFQ can only be attached while the Purchase Requisition is in SCM Approval stage."))
        if not self.is_po_link and not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only configured RFQ Create users can attach an existing RFQ."))
        if self.reset_requested or self.cancel_requested:
            raise UserError(_("Resolve the pending reset/cancellation request before attaching an RFQ."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Attach Existing RFQ"),
            "res_model": "softeko.purchase.requisition.attach.rfq.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("softeko_purchase_requisition.view_softeko_purchase_requisition_attach_rfq_wizard_form").id,
            "target": "new",
            "context": {"default_requisition_id": self.id},
        }


class PurchaseRequisitionAttachRfqWizard(models.TransientModel):
    _name = "softeko.purchase.requisition.attach.rfq.wizard"
    _description = "Attach Existing RFQ to Purchase Requisition"

    requisition_id = fields.Many2one(
        "softeko.purchase.requisition",
        string="Purchase Requisition",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="requisition_id.company_id",
        readonly=True,
    )
    linked_rfq_ids = fields.Many2many(
        "purchase.order",
        compute="_compute_linked_rfq_ids",
    )
    rfq_id = fields.Many2one(
        "purchase.order",
        string="Existing RFQ",
        required=True,
        help="Only unconfirmed RFQs from the same company can be attached. The PR material lines are appended to the selected RFQ; existing RFQ lines are preserved.",
    )

    @api.depends("requisition_id")
    def _compute_linked_rfq_ids(self):
        for wizard in self:
            wizard.linked_rfq_ids = wizard.requisition_id.purchase_order_ids if wizard.requisition_id else False

    def action_attach(self):
        self.ensure_one()
        pr = self.requisition_id
        rfq = self.rfq_id

        if not pr or not rfq:
            raise UserError(_("Select an RFQ to attach."))
        if pr.state != "rfq":
            raise UserError(_("The Purchase Requisition is no longer in SCM Approval stage."))
        if not pr.is_po_link and not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only configured RFQ Create users can attach an existing RFQ."))
        if pr.reset_requested or pr.cancel_requested:
            raise UserError(_("Resolve the pending reset/cancellation request before attaching an RFQ."))
        if rfq.company_id != pr.company_id:
            raise UserError(_("The RFQ company must match the Purchase Requisition company."))
        if rfq.state not in RFQ_STATES:
            raise UserError(_("Only an unconfirmed RFQ can be attached. Confirmed, done, or cancelled Purchase Orders are not allowed."))
        if pr in rfq._get_linked_requisitions():
            raise UserError(_("This RFQ is already attached to %s.") % pr.name)

        # Keep all existing RFQ lines and append this PR's material lines.
        # There is intentionally no PR-line/RFQ-line traceability and no quantity matching.
        existing_sequences = rfq.order_line.mapped("sequence")
        next_sequence = (max(existing_sequences) if existing_sequences else 0) + 10
        line_commands = []

        for line in pr.material_line_ids.sorted("sequence"):
            if line.display_type:
                line_commands.append(Command.create({
                    "sequence": next_sequence,
                    "display_type": line.display_type,
                    "name": line.name or "",
                }))
                next_sequence += 10
                continue

            if not line.product_id:
                continue

            line_commands.append(Command.create({
                "sequence": next_sequence,
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "product_qty": line.product_qty,
                "product_uom_id": (line.product_uom_id or line.product_id.uom_id).id,
                "date_planned": fields.Datetime.to_datetime(line.required_date) if line.required_date else fields.Datetime.now(),
            }))
            next_sequence += 10

        if not line_commands:
            raise UserError(_("The Purchase Requisition has no material lines to append to the RFQ."))

        # Command.link adds the PR to the RFQ header; Command.create appends lines.
        # No Command.set/clear is used for order_line, so pre-existing RFQ lines remain untouched.
        rfq.write({
            "pr_requisition_ids": [Command.link(pr.id)],
            "order_line": line_commands,
        })

        pr.message_post(body=_(
            "Existing RFQ %s attached by %s. %s PR line(s) were appended; existing RFQ lines were preserved."
        ) % (rfq.name, self.env.user.display_name, len(line_commands)))
        rfq.message_post(body=_(
            "Purchase Requisition %s attached by %s. %s PR line(s) were appended; existing RFQ lines were preserved."
        ) % (pr.name, self.env.user.display_name, len(line_commands)))

        return {"type": "ir.actions.client", "tag": "reload"}
