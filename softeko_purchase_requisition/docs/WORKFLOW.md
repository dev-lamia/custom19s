# Functional Workflow — 19.0.0.7.0

The module supports **three primary Purchase Requisition flows**. RFQ/PO linkage is document-level; there is no line traceability or quantity matching.

## Flow 1 — Normal Purchase Requisition

1. Requester creates the PR in **Draft** and enters material lines.
2. Requester submits it to **Submitted to Manager**.
3. Manager approves it to **SCM Approval**.
4. RFQ Create user either:
   - creates a new RFQ from the PR; or
   - uses **Attach Existing RFQ**.
5. If **Attach Existing RFQ** is used, the existing RFQ lines are preserved and the PR material lines are appended to the end of the selected RFQ.
6. SCM approves the PR. No product or quantity equality check is performed.
7. PR moves to **Finance Approval**.
8. Finance approves it to **Issue PO**.
9. PO Issuer confirms a linked RFQ/PO.
10. PR becomes **Done** at document level.

**Stage sequence:**

`Draft → Submitted to Manager → SCM Approval → Finance Approval → Issue PO → Done`

## Flow 2 — Purchase Requisition with Sale Order

This flow applies when either:

- a Sale Order is selected on a Draft PR; or
- the user clicks **Create PR** from a Sale Order.

The Sale Order relationship adds one stage after Finance approval.

1. **Draft**
2. **Submitted to Manager**
3. **SCM Approval**
4. **Finance Approval**
5. **Confirm Sale Order**
6. **Issue PO**
7. **Done**

When Finance approves, the PR moves to **Confirm Sale Order** and the requester receives the Sale Order confirmation activity. When the linked Sale Order is confirmed through the normal Sales workflow, the PR automatically moves to **Issue PO** and the PO Issuer activity is created.

**Stage sequence:**

`Draft → Submitted to Manager → SCM Approval → Finance Approval → Confirm Sale Order → Issue PO → Done`

## Flow 3 — Office Supply Purchase Requisition

Office Supply requests use the short procurement route and bypass Manager and SCM approval.

1. Office Supply creates/links the PR.
2. PR enters **Finance Approval**.
3. Finance approves it to **Issue PO**.
4. PO Issuer creates/confirms the purchase document.
5. PR becomes **Done**.

Reset/resubmit preserves the Office Supply shortcut back to Finance.

**Stage sequence:**

`Draft / Office Supply → Finance Approval → Issue PO → Done`

## Attach Existing RFQ

The button is available to configured RFQ Create users while the PR is in **SCM Approval**.

Eligible purchase documents:

- same company as the PR;
- `draft`, `sent`, or `to approve`;
- not already linked to this PR.

When attached:

- the PR is linked to the RFQ header;
- all existing RFQ lines stay exactly where they are;
- the PR's sections, notes, and product lines are appended after the current RFQ lines;
- no existing RFQ line is deleted, replaced, merged, or assigned to a PR line;
- no quantity equality/allocation validation is performed.

Multiple PRs may be attached to the same RFQ. Each attachment appends that PR's lines as new RFQ lines.

## Create RFQ

**Create RFQ** opens a new RFQ prefilled with the PR's material lines and links the PR at document level. It does not create PR-line traceability metadata.

## Reset to Draft

### No confirmed PO

An authorized stakeholder enters a reason and the PR returns to Draft. Existing RFQs stay linked. After resubmission and Manager approval, a PR with an existing RFQ pauses in **RFQ REVIEW** so Procurement can review the linked RFQ before sending it for SCM approval. No automatic line synchronization or quantity validation is performed.

### Reset notification matrix

When the reset is completed, routing is based on business role and direct-recipient delivery:

| Recipient | Message / activity | Rule |
|---|---|---|
| PR `requester_id` | Review/amend and resubmit direct notification + **Requisition Review** activity | Sent only when requester is not the reset actor |
| Approval `link_user_ids` | Review linked RFQ(s) after resubmission direct notification | Sent only when linked unconfirmed RFQ(s) exist; reset actor is excluded |
| Reset actor | No directed reset notification and no Requisition Review activity | Excluded even when the actor follows the PR or also holds another configured role |
| RFQ `user_id` | No automatic reset notification | Receives RFQ-review message only if also configured in `link_user_ids` and is not the reset actor |

For an immediate reset, PR chatter keeps one completed-reset audit entry identifying the reset actor, previous stage, and reason. A reset blocked by a confirmed PO keeps a request audit while pending and a completion audit later. Audit entries are posted with follower notification disabled, and internal reset writes suppress automatic tracking mail. The two role-specific messages are sent with `message_notify(..., notify_skip_followers=True)`, so follower subscriptions cannot widen the recipient list and the role messages do not appear as duplicate chatter posts.

If one non-reset user holds both roles (requester and RFQ Link user), that user may receive both messages because they own both follow-up responsibilities.

### Confirmed PO exists

The PR receives **RESET REQUESTED** until the linked confirmed PO dependency is resolved using normal Odoo controls. Shared RFQ/PO documents are handled at document level because there is no PR-line ownership.

## Cancellation

Cancellation is document-dependency based:

- no active linked RFQ/PO: cancel immediately;
- unconfirmed RFQ: Procurement resolves/unlinks/cancels the RFQ as appropriate;
- confirmed PO: PO Issuer resolves the PO through standard Odoo controls;
- shared RFQs/POs must be handled carefully because one purchase document can be linked to multiple PRs.

## Send Back vs Reset vs Cancel

- **Send Back** returns the PR one approval stage for correction.
- **Reset to Draft** reopens the procurement lifecycle for amendment.
- **Cancel** terminates the PR after purchase-document dependencies are resolved.
