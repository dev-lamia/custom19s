from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare


FINANCE_GROUP = "sale_finance_advance_control.group_finance_approver"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    payment_verification_state = fields.Selection(
        [
            ("not_submitted", "Not Submitted"),
            ("pending", "Pending Finance Review"),
            ("verified", "Verified"),
            ("rejected", "Rejected"),
        ],
        string="Advance Payment Verification",
        default="not_submitted",
        copy=False,
        tracking=True,
        index=True,
        readonly=True,
    )
    advance_payment_amount = fields.Monetary(
        string="Advance Payment Claimed",
        currency_field="currency_id",
        copy=False,
        readonly=True,
        tracking=True,
    )
    advance_payment_reference = fields.Char(
        string="Advance Payment Reference",
        copy=False,
        readonly=True,
    )
    payment_proof_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Payment Proof Attachment",
        copy=False,
        readonly=True,
    )
    payment_verified_by = fields.Many2one(
        "res.users",
        string="Verified By",
        copy=False,
        readonly=True,
    )
    payment_verified_on = fields.Datetime(
        string="Verified On",
        copy=False,
        readonly=True,
    )
    production_release_state = fields.Selection(
        [("hold", "On Hold"), ("released", "Released")],
        string="Production Release",
        default="hold",
        copy=False,
        tracking=True,
        readonly=True,
    )
    production_released_by = fields.Many2one(
        "res.users",
        string="Production Released By",
        copy=False,
        readonly=True,
    )
    production_released_on = fields.Datetime(
        string="Production Released On",
        copy=False,
        readonly=True,
    )

    def _check_finance_access(self):
        if not self.env.user.has_group(FINANCE_GROUP):
            raise AccessError(_("Only Finance Approvers can perform this action."))

    @api.model_create_multi
    def create(self, vals_list):
        finance = self.env.user.has_group(FINANCE_GROUP)
        for vals in vals_list:
            if vals.get("state") == "sale":
                raise UserError(
                    _("Create a quotation first and confirm it through the normal workflow.")
                )
            if not finance and (
                vals.get("payment_verification_state") in ("verified", "rejected")
                or vals.get("payment_verified_by")
                or vals.get("payment_verified_on")
                or vals.get("production_release_state") == "released"
                or vals.get("production_released_by")
                or vals.get("production_released_on")
            ):
                raise AccessError(_("Only Finance can set approval fields."))
        return super().create(vals_list)

    def write(self, vals):
        finance = self.env.user.has_group(FINANCE_GROUP)
        protected_fields = {
            "payment_verified_by",
            "payment_verified_on",
            "production_release_state",
            "production_released_by",
            "production_released_on",
        }
        if not finance and any(key in vals for key in protected_fields):
            raise AccessError(_("Only Finance can modify approval fields."))

        if not finance and "payment_verification_state" in vals:
            if vals["payment_verification_state"] != "pending":
                raise AccessError(_("Only Finance can verify or reject payments."))
            if any(order.state not in ("draft", "sent") for order in self):
                raise UserError(_("Payment proof can only be submitted on a quotation."))
            if any(order.payment_verification_state == "verified" for order in self):
                raise UserError(_("A verified payment cannot be resubmitted by Sales."))

        if not finance and any(
            key in vals
            for key in (
                "advance_payment_amount",
                "advance_payment_reference",
                "payment_proof_attachment_id",
            )
        ):
            if any(order.state not in ("draft", "sent") for order in self):
                raise UserError(_("Advance payment evidence is locked after confirmation."))
            if any(order.payment_verification_state == "verified" for order in self):
                raise UserError(_("Finance must reject verification before changing proof."))

        if vals.get("state") == "sale":
            self._check_finance_access()
            unverified = self.filtered(
                lambda order: order.state != "sale"
                and order.payment_verification_state != "verified"
            )
            if unverified:
                raise UserError(
                    _("Finance must verify the advance payment before confirming %s.")
                    % ", ".join(unverified.mapped("name"))
                )

        return super().write(vals)

    def action_open_payment_proof_wizard(self):
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_("Payment proof is accepted on quotations only."))
        if self.payment_verification_state == "verified":
            raise UserError(_("Finance already verified this payment."))
        return {
            "name": _("Submit Advance Payment Proof"),
            "type": "ir.actions.act_window",
            "res_model": "sale.finance.payment.submit.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "sale_finance_advance_control.view_payment_submit_wizard_form"
            ).id,
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
                "default_amount": self.advance_payment_amount or False,
                "default_payment_reference": self.advance_payment_reference or False,
            },
        }

    def action_verify_advance_payment(self):
        self._check_finance_access()
        for order in self:
            if order.state not in ("draft", "sent"):
                raise UserError(_("Only open quotations can be payment verified."))
            if order.payment_verification_state != "pending":
                raise UserError(_("Submit payment proof for %s first.") % order.name)
            if not order.payment_proof_attachment_id or order.advance_payment_amount <= 0:
                raise UserError(_("Payment proof and a positive amount are required."))
            # Human attestation. This button does not query the bank.
            order.write({
                "payment_verification_state": "verified",
                "payment_verified_by": self.env.user.id,
                "payment_verified_on": fields.Datetime.now(),
            })
            order.message_post(
                body=_("Finance verified the advance payment against the bank."),
                subtype_xmlid="mail.mt_note",
            )
            # Only close the matching finance-review activity, not unrelated tasks.
            tasks = order.activity_ids.filtered(
                lambda activity: activity.summary == "Verify advance payment"
                and activity.user_id == self.env.user
            )
            if tasks:
                tasks.action_feedback(feedback=_("Bank payment verified."))
        return True

    def action_reject_advance_payment(self):
        self._check_finance_access()
        for order in self:
            if order.state not in ("draft", "sent"):
                raise UserError(_("Only open quotations can be rejected."))
            if order.payment_verification_state not in ("pending", "verified"):
                raise UserError(_("There is no payment submission to reject."))
            order.write({
                "payment_verification_state": "rejected",
                "payment_verified_by": False,
                "payment_verified_on": False,
            })
            order.message_post(
                body=_("Finance rejected the submitted proof. Sales must resubmit it."),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_confirm(self):
        if any(order.state in ("draft", "sent") for order in self):
            self._check_finance_access()
            unverified = self.filtered(
                lambda order: order.state in ("draft", "sent")
                and order.payment_verification_state != "verified"
            )
            if unverified:
                raise UserError(
                    _("Verify advance payment before confirming: %s")
                    % ", ".join(unverified.mapped("name"))
                )
            for order in self.filtered(lambda record: record.state in ("draft", "sent")):
                if (
                    not order.payment_proof_attachment_id
                    or order.advance_payment_amount <= 0
                    or float_compare(
                        order.advance_payment_amount,
                        order.amount_total,
                        precision_rounding=order.currency_id.rounding,
                    ) > 0
                ):
                    raise UserError(
                        _("The approved advance for %s has invalid or missing proof/amount.")
                        % order.name
                    )
        return super().action_confirm()

    def action_release_production(self):
        self._check_finance_access()
        for order in self:
            if order.state != "sale" or order.payment_verification_state != "verified":
                raise UserError(_("Confirm the order after payment verification first."))
            if not order.invoice_ids.filtered(
                lambda invoice: invoice.move_type == "out_invoice"
                and invoice.state == "posted"
            ):
                raise UserError(
                    _("Post a customer invoice for %s before production release.")
                    % order.name
                )
            if order.production_release_state == "released":
                continue
            order.write({
                "production_release_state": "released",
                "production_released_by": self.env.user.id,
                "production_released_on": fields.Datetime.now(),
            })
            order.message_post(
                body=_("Finance released this order for artwork / production."),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _create_invoices(self, grouped=False, final=False, date=None):
        self._check_finance_access()
        if any(order.state != "sale" for order in self):
            raise UserError(_("A Sales Order must be confirmed before invoicing."))
        return super()._create_invoices(grouped=grouped, final=final, date=date)
