# -*- coding: utf-8 -*-
{
    "name": "Purchase Requisition",
    "version": "19.0.0.8.10",
    "category": "Customizations",
     "author": "Softeko_HUMAYRA",
    "summary": "Purchase Requisition approvals, document-level RFQ/PO linking, controlled reset/cancel and Alternative RFQ support",
    "description": """
Purchase Requisition for Odoo 19 provides the module's multi-stage procurement request workflow,
company-aware activities and approvals, document-level RFQ/PO linking, Sale Order and Office Supply
integration, delivery scheduling, controlled Reset to Draft and cancellation, and compatibility with
Odoo Purchase Agreements / Alternative RFQs. PR-to-RFQ line traceability and quantity reconciliation
are intentionally not used. Existing RFQs can be attached at document level while preserving their
current lines and appending the newly attached PR's material lines.
See README.md and docs/ for functional, technical, upgrade and UAT documentation.
""",
    
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "product",
        "accountant",
        "purchase",
        "purchase_requisition",
        "sale_management",
    ],
    "data": [
        "security/pr_security_groups.xml",
        "security/ir.model.access.csv",
        "security/mail_activity_pr_rule.xml",
        "security/purchase_requisition_rule.xml",
        "data/purchase_requisition_sequence.xml",
        "data/mail_activity_type.xml",
        "views/purchase_change_request_wizard_views.xml",
        "views/purchase_attach_rfq_wizard_views.xml",
        "views/purchase_requisition_views.xml",
        "views/purchase_requisition_delivery_views.xml",
        "views/purchase_order_requisition_views.xml",
        "views/res_partner_views.xml",
        "views/sale_order_view.xml",
        "views/purchase_requisition_approval_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
