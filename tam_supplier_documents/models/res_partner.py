from odoo import api, fields, models, _
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = ["res.partner", "mail.thread", "mail.activity.mixin"]

    vendor_document_ids = fields.One2many(
        comodel_name="vendor.document",
        inverse_name="partner_id",
        string="Vendor Documents",
    )
    expired_vendor_document_type_ids = fields.Many2many(
        comodel_name="supplier.document.type",
        compute="_compute_expired_vendor_document_types",
        string="Expired Vendor Document Types",
        store=False,
    )

    expired_vendor_document_type_names = fields.Char(
        compute="_compute_expired_vendor_document_types",
        string="Expired Vendor Document Types (Names)",
        store=False,
    )


    @api.model
    def cron_notify_vendor_docs_expiry_30_days(self):
        today = fields.Date.today()
        target_date = today + timedelta(days=30)

        VendorDoc = self.env["vendor.document"]
        docs = VendorDoc.search([
            ("expiry_date", ">=", today),
            ("expiry_date", "<=", target_date),
            ("stop_notifications", "=", False),
        ])

        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return

        for doc in docs:
            if doc.last_notified_on == today:
                continue

            vendor = doc.partner_id
            if not vendor:
                continue

            dept = doc.department_id
            manager_user = dept.manager_id.user_id if (dept and dept.manager_id and dept.manager_id.user_id) else False
            if not manager_user:
                continue

            vendor.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=manager_user.id,
                date_deadline=today,
                summary=_("Vendor Document Expiry Reminder (30 Days)"),
                note=_(
                    "Vendor: <b>%s</b><br/>"
                    "Document Type: <b>%s</b><br/>"
                    "Expires on: <b>%s</b>"
                ) % (vendor.display_name, doc.type_id.display_name, doc.expiry_date),
            )

            doc.last_notified_on = today
            _logger.info(
                "Scheduled expiry notification activity for Vendor Document ID %s (Vendor: %s, Document Type: %s, Expiry Date: %s)",
                doc.id, vendor.display_name, doc.type_id.display_name, doc.expiry_date
            )
            
    @api.depends("vendor_document_ids.expiry_date", "vendor_document_ids.type_id")
    def _compute_expired_vendor_document_types(self):
        today = fields.Date.today()
        limit_date = today + timedelta(days=30)

        for partner in self:
            # block if expiry_date is within next 30 days (including already expired)
            blocked_docs = partner.vendor_document_ids.filtered(
                lambda d: d.expiry_date and d.expiry_date <= limit_date
            )
            types = blocked_docs.mapped("type_id")

            partner.expired_vendor_document_type_ids = types
            partner.expired_vendor_document_type_names = ", ".join(types.mapped("display_name"))
