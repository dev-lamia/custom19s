# Validation Checklist — 19.0.0.7.0

- **Attach Existing RFQ** allows only same-company unconfirmed RFQs (`draft`, `sent`, `to approve`).
- Existing RFQ `order_line` records are preserved.
- PR material lines are appended as new RFQ lines.
- No PR-line traceability/sync metadata is created.
- No quantity allocation/matching validation is executed.
- A manually attached Sale Order and **Create PR** from Sale Order both use **Confirm Sale Order** after Finance Approval.
- Normal PR bypasses Confirm Sale Order and goes Finance Approval → Issue PO.
- Office Supply uses its direct Finance Approval → Issue PO route.

- Reset requester message goes only to PR `requester_id` when that requester did not perform the reset.
- **Requisition Review** activity is assigned to that requester and never to the reset actor solely because they reset the PR.
- Linked-RFQ reset message goes only to configured Approval **RFQ Link** users (`link_user_ids`).
- RFQ `user_id` is not automatically included in reset notifications.
- Reset actor is excluded from both directed reset notification recipient sets.
- Directed reset messages use `message_notify(..., notify_skip_followers=True)`; PR followers cannot be added implicitly.
- The reset actor has no `mail.notification` for the requester/RFQ-Link role messages, even if the actor is a PR follower or Finance Approver.
- Role messages are `user_notification` records and do not appear as duplicate PR chatter posts.
- For an immediate reset, chatter records one non-notifying completion audit with the reset actor, previous stage, and reason. If a confirmed PO blocks the reset, chatter keeps a non-notifying request audit while pending and a completion audit when the reset is finalized.

## 19.0.0.8.0 validation additions

1. **Manager bypass by company**
   - In Company A Approval Configuration, add an employee to **No Manager Approval Employees**.
   - Submit a normal PR for that employee in Company A.
   - Expected: no manager activity is created; PR moves directly to RFQ/PO Link and RFQ Create activities are created.
   - Submit for the same user in another company where the employee is not selected.
   - Expected: normal Manager Approval remains required.

2. **Manager activity ownership**
   - Submit a PR requiring Manager Approval.
   - As the requester, try to mark the manager's PR workflow activity Done from the activity UI.
   - Expected: `Only the assigned user or an Administrator can modify this activity.`
   - As a different manager/approver, try to execute Manager Approve without owning the manager activity.
   - Expected: approval is blocked because the required activity is not assigned to that user.

3. **Approval Configuration multi-company UI**
   - Open Purchase Requisition -> Configuration -> Approval.
   - Expected: normal list/form view, filtered to the currently active company.
   - Switch active company and reopen/reload the list.
   - Expected: records for the newly active company are shown; Create defaults Company to that company.
   - A second config for the same company must be rejected by the unique company constraint.

4. **PR global search by RFQ/PO**
   - Search the PR list using a PR number, project/cost center, and an RFQ/PO number.
   - Expected: no `Cannot use 'any' with non-relational fields` RPC error.
   - Verify Has RFQ/PO and No RFQ/PO filters still work.
