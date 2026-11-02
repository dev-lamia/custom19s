# Purchase Requisition — Odoo 19

Purchase Requisition provides the module's approval workflow, RFQ/PO document linking, Sale Order and Office Supply integration, delivery scheduling, and controlled reset/cancellation.

## Version 19.0.0.7.0

This version intentionally uses **document-level PR ↔ RFQ/PO linking only**. There is no PR-line ↔ RFQ-line traceability, sync key, allocation matching, confirmed/remaining quantity calculation, partial-procurement calculation, or over-purchase quantity validation.

### Attach Existing RFQ

In **SCM Approval**, an RFQ Create user can click **Attach Existing RFQ** and select a same-company unconfirmed RFQ in `draft`, `sent`, or `to approve`.

The action now does two things:

1. attaches the PR to the RFQ at header/document level; and
2. **appends the PR's material lines to the existing RFQ**.

Existing RFQ lines are never cleared or replaced. Sections/notes from the PR are also appended. The new lines have no PR-line ownership field and no quantity-matching logic.

Confirmed, done, or cancelled purchase orders cannot be newly attached.

## Three supported PR flows

### 1. Normal PR

**Draft → Submitted to Manager → SCM Approval → Finance Approval → Issue PO → Done**

### 2. Sale Order PR

When a Sale Order is attached manually in Draft, or the PR is created using **Create PR** from a Sale Order:

**Draft → Submitted to Manager → SCM Approval → Finance Approval → Confirm Sale Order → Issue PO → Done**

Finance approval moves the PR to **Confirm Sale Order**. When the linked Sale Order is confirmed, the PR automatically advances to **Issue PO**.

### 3. Office Supply PR

**Draft / Office Supply creation → Finance Approval → Issue PO → Done**

Office Supply keeps its direct Finance path and does not use the Manager/SCM stages.

## PO confirmation

A PR-linked RFQ/PO can be confirmed only when all linked PRs are in **Issue PO** and no reset/cancellation request is pending. There is no product-line or quantity reconciliation.

When any linked PO is confirmed, a PR in **Issue PO** is completed at document level.

## Reset to Draft notification routing

When a PR actually returns to **Draft**, reset communication is split into one audit record and strict direct notifications:

- **PR chatter:** an immediate reset records one completed-reset audit entry with who reset the PR, previous stage, and reason. If a confirmed PO blocks the reset, a separate request audit is kept while pending and a completion audit is added later. Audit entries do not notify followers.
- **PR requester (`requester_id`)** receives the review/amend/resubmit direct notification and owns the **Requisition Review** activity, unless the requester is the reset actor.
- **RFQ Link users (`link_user_ids`)** receive the linked-RFQ review direct notification only when an unconfirmed linked RFQ exists.
- **Reset actor (`env.user`)** is removed from both direct recipient sets. Being a PR follower, Finance Approver, SCM Approver, PO Issuer, requester, or RFQ Link user does not make the actor receive these two reset messages.
- **RFQ `user_id`** is not automatically included. The buyer receives the RFQ-review notification only when separately configured in **Approval Setup → RFQ Link** and they did not perform the reset.

The two role messages use Odoo 19 `message_notify(..., notify_skip_followers=True)` rather than `message_post()`. They are `user_notification` records, so only explicit recipients are notified and the two role messages do not appear as duplicate chatter entries. If the same non-reset user is both requester and RFQ Link user, that user can still legitimately receive both role-specific notifications.


### 19.0.0.8.10 regression hardening
Requester cancellation no longer requires Purchase ACLs for internal dependency fields; Sale Order confirmation uses the live SO state; RFQ review role checks are user-context safe.
