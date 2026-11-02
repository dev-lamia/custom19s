# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    workflow_type = env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

    # If 19.0.0.3.0 was installed successfully, preserve its explicit markers.
    # The old column is intentionally left in PostgreSQL as harmless legacy data;
    # dropping it during a functional module upgrade would be unnecessarily risky.
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'mail_activity'
           AND column_name = 'pr_workflow_activity'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE mail_activity
               SET activity_type_id = %s
             WHERE pr_workflow_activity IS TRUE
        """, [workflow_type.id])

    # Best-effort conversion for older PR workflow activities created as generic
    # To-Dos before the explicit marker existed. Do not touch arbitrary manual To-Dos.
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
        "Reset PO(s) to Draft",
        "Complete Reset to Draft",
        "Cancel/Resolve PO dependency",
        "Review split RFQ allocation",
    )
    legacy_activities = env["mail.activity"].sudo().search([
        ("res_model", "=", "softeko.purchase.requisition"),
        ("activity_type_id", "!=", workflow_type.id),
    ])
    legacy_activities.filtered(
        lambda activity: any(token in (activity.summary or "") for token in workflow_summary_tokens)
    ).write({"activity_type_id": workflow_type.id})
