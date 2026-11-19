from markupsafe import Markup, escape

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PaymentSubmitWizard(models.TransientModel):
    _name = "sale.finance.payment.submit.wizard"
    _description = "Submit Advance Payment Proof"

    sale_order_id = fields.Many2one(
        "sale.order", string="Quotation", required=True, readonly=True
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="sale_order_id.currency_id"
    )
    amount = fields.Monetary(
        string="Advance Amount", currency_field="currency_id", required=True
    )
    payment_reference = fields.Char(string="Bank/Transfer Reference")
    payment_proof = fields.Binary(
        string="Payment Copy", required=True, attachment=False
    )
    payment_filename = fields.Char(string="File Name")

    def action_submit(self):
        self.ensure_one()
        order = self.sale_order_id
        order.check_access("write")
        if order.state not in ("draft", "sent"):
            raise UserError(_("Only an open quotation accepts payment proof."))
        if order.payment_verification_state == "verified":
            raise UserError(_("Finance already verified the payment."))
        if self.amount <= 0:
            raise UserError(_("Advance amount must be greater than zero."))
        if float_compare(
            self.amount, order.amount_total, precision_rounding=order.currency_id.rounding
        ) > 0:
            raise UserError(_("Advance amount must not exceed the quotation total."))
        if not self.payment_proof:
            raise UserError(_("Please attach the customer payment copy."))

        finance_group = self.env.ref(
            "sale_finance_advance_control.group_finance_approver"
        )
        finance_users = finance_group.sudo().all_user_ids.filtered(
            lambda user: user.active and not user.share
        )
        if not finance_users:
            raise UserError(
                _("Please assign at least one Finance Approver user before submitting.")
            )

        attachment = self.env["ir.attachment"].create({
            "name": self.payment_filename or "advance_payment_proof",
            "type": "binary",
            "datas": self.payment_proof,
            "res_model": "sale.order",
            "res_id": order.id,
        })
        order.write({
            "advance_payment_amount": self.amount,
            "advance_payment_reference": self.payment_reference,
            "payment_proof_attachment_id": attachment.id,
            "payment_verification_state": "pending",
        })
        order.message_post(
            body=Markup(
                "Advance payment proof submitted by Sales. "
                "Amount: <b>%s %s</b>; Reference: <b>%s</b>. "
                "Finance must check the bank before verifying."
            ) % (
                escape(order.currency_id.name),
                escape(str(self.amount)),
                escape(self.payment_reference or "Not provided"),
            ),
            attachment_ids=attachment.ids,
            subtype_xmlid="mail.mt_note",
        )
        todo = self.env.ref("mail.mail_activity_data_todo")
        for finance_user in finance_users:
            already_scheduled = order.activity_ids.filtered(
                lambda activity: activity.user_id == finance_user
                and activity.activity_type_id == todo
                and activity.summary == "Verify advance payment"
            )
            if not already_scheduled:
                order.activity_schedule(
                    activity_type_id=todo.id,
                    user_id=finance_user.id,
                    summary="Verify advance payment",
                    note=_("Check the attached bank payment copy and the credited amount."),
                )
        return {"type": "ir.actions.act_window_close"}
