# Upgrade Notes — 19.0.0.7.0

1. Replace the existing `softeko_purchase_requisition` addon directory with this version.
2. Restart Odoo and upgrade **Purchase Requisition** (`-u softeko_purchase_requisition`).
3. Clear browser assets/cache if old view text remains visible.
4. Test **Attach Existing RFQ** using an RFQ that already contains lines. Existing lines must remain, and the selected PR's lines must be appended.
5. Test all three stage flows: Normal PR, Sale Order PR, and Office Supply PR.
6. Test Reset to Draft with three distinct users: reset actor, PR requester, and RFQ Link user. Make the reset actor a PR follower/Finance Approver. Verify only requester and RFQ Link receive their direct role messages, the reset actor has no `mail.notification`, and the PR chatter shows only the reset audit entry rather than the two role messages.

## Data model

Version 19.0.0.7.0 keeps the simplified 19.0.0.4.0 data model: document-level PR ↔ RFQ/PO links remain, while PR-line/RFQ-line ownership and quantity-reconciliation fields remain removed.

No new persistent field is required by 19.0.0.7.0. This release changes the reset mail-delivery mechanism: role messages use direct `message_notify` delivery with follower expansion disabled, while reset chatter entries are audit-only and non-notifying.
