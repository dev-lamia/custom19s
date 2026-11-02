# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Legacy workflow migration kept safe for databases upgrading across 19.0.0.3.0.

    Line-level PR/RFQ traceability was removed in 19.0.0.4.0, so this migration no
    longer creates/backfills sync keys or purchase-order-line mappings.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    workflow_summary_tokens = (
        "Approve Purchase Requisition",
        "Requisition Review",
        "Create RFQ/PO & Link",
        "ready for SCM approval",
        "PR ready for Finance approval",
        "Confirm Sale Order",
        "Create Purchase Order",
        "Issue Purchase Order",
        "Review Purchase Requisition",
        "Review RFQ/PO & Link",
    )
    workflow_type = env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
    legacy_activities = env["mail.activity"].sudo().search([
        ("res_model", "=", "softeko.purchase.requisition"),
        ("activity_type_id", "!=", workflow_type.id),
    ])
    legacy_activities.filtered(
        lambda activity: any(token in (activity.summary or "") for token in workflow_summary_tokens)
    ).write({"activity_type_id": workflow_type.id})

    requisitions = env["softeko.purchase.requisition"].with_context(active_test=False).search([])
    for requisition in requisitions:
        users = requisition.requester_id | requisition.activity_ids.mapped("user_id")
        manager = requisition._get_requester_manager_user()
        if manager:
            users |= manager
        users |= requisition.message_ids.mapped("author_id.user_ids").filtered(lambda u: not u.share)
        requisition._register_stakeholders(users)
