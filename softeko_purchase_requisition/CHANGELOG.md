## 19.0.0.8.10 - 2026-09-15

- Fixed requester cancellation without Purchase Order access by handling internal RFQ/PO dependency relations under sudo after lifecycle authorization.
- Fixed immediate cancellation and dependency-based cancellation clearing `cancel_blocking_po_ids` for non-Purchase users.
- Hardened confirmed-PO Reset finalization so requesters without Purchase access can complete Reset after the blocking PO returns to Draft.
- Made Sale Order confirmation use the linked Sale Order's live state so `Confirm Sale Order` reliably advances the PR to `Issue PO`.
- Made user-dependent PR role booleans recompute per user (`uid`) and hardened post-reset RFQ review authorization against the configured RFQ Create users directly.
- Updated current-workflow tests so final PO confirmation is independent of the database Purchase double-validation threshold.

# 19.0.0.8.9

- Isolated the current Purchase Requisition workflow regression suite from `hr.employee.create()` overrides in unrelated HR modules.
- Manager/requester hierarchy is stubbed in-memory only for tests; PR, RFQ/PO, activities, users, role configuration and access checks still use real ORM records.
- Prevents external HR failures (for example a non-stored `hr.version.date_start` ordering issue) from aborting PR tests in `setUpClass`.

# 19.0.0.8.8

- Replaced obsolete/fragile lifecycle tests with 24 workflow-driven regression tests.
- Covered all three live flows: normal PR, Sale Order PR, and Office Supply PR.
- Added Reset-to-Draft coverage by stage/role: requester, manager, RFQ Create, SCM, Finance, PO Issuer.
- Added confirmed-PO pending reset/finalize coverage and post-reset RFQ review/resubmit coverage.
- Added cancellation coverage for no dependency, draft RFQ, confirmed PO, Sale Order, and Office Supply final cancellation.
- Added Office Supply tests for requester-without-Purchase-access reset, Finance reset, Issue PO reset, and Send Back blocking.
- Added manual To-Do preservation and non-stakeholder authorization coverage.

# 19.0.0.8.7

- Fix Office Supply requester Reset to Draft from Finance stage: initialise the RFQ recordset so Office Supply PRs, which bypass SCM/RFQ linking, do not crash with `UnboundLocalError: open_rfqs`.
- Keep RFQ review disabled for Office Supply Finance resets.
- Update regression-test user group field references from Odoo 18-style `groups_id` to Odoo 19 `group_ids`.
- Add a focused regression test for the Office Supply Finance reset path.

## 19.0.0.8.6
- Allow an Office Supply PR requester to Reset to Draft from Finance Approval without requiring Purchase Order access.
- Hide and server-block Finance Send Back for Office Supply PRs; Reset to Draft is the correction path.
- Run computed Purchase Order linkage in sudo mode and use controlled sudo only for reset lifecycle bookkeeping.

## 19.0.0.8.4

## 19.0.0.8.5

- Fixed reset/cancel activity cleanup accidentally triggering Manager/SCM/Finance approval through the Mark Done approval bridge.
- Added explicit `pr_system_activity_cleanup` context for automatic workflow activity completion.
- Lifecycle cleanup now completes PR workflow activities with audit feedback instead of falling back to silent unlink on errors.
- Hardened automatic/stale activity cleanup so only a genuine user Mark Done action can invoke an approval-stage business action.

- Enforced one Approval Configuration per company at ORM level in addition to the SQL constraint, including Create/Duplicate protection.
- Preserved multi-assignee activity audit history by closing other same-stage activities with feedback instead of unlinking them.

## 19.0.0.8.3

- Fixed Manager Approve and PR Workflow activity **Done** failing with "The required approval activity was not found for this stage." on normal submissions.
- The actual Manager Approval activity remains strictly required and must belong to the approving manager.
- The optional post-reset `Review Purchase Requisition ...` activity is now cleanup-only and no longer blocks approval when absent.
- SCM and Finance approval-stage activity validation remains strict only for their actual approval activity; optional RFQ/create cleanup activities remain non-blocking.

## 19.0.0.8.2

- PR Manager, SCM and Finance approval activities now treat **Mark Done** as the same secured business approval as the corresponding PR Approve button.
- Added recursion protection so an activity-originated approval does not try to complete the same activity twice.
- Preserved normal Mark Done behaviour for operational PR activities such as RFQ/PO creation/review and PO issue.
- Activity-originated approvals use standardized audit feedback (`Approved by Manager/SCM/Finance: <user>`).

# 19.0.0.8.1

- Approval Configuration list now shows records for all companies currently enabled in the Odoo company selector, instead of only the main active company.
- New Approval Configuration records still default to the main active company.
- Manager Approval Exceptions explanatory note restored outside the form group so it uses the full sheet width.

# 19.0.0.8.0 - 2026-08-19

- Added company-specific **No Manager Approval Employees** to Approval Configuration; selected employees submit directly to RFQ/PO Link without changing HR hierarchy.
- Replaced the form-only singleton menu behavior with normal list/form Approval Configuration views filtered to the active company while retaining one configuration record per company.
- Hardened PR workflow activity completion: manager approval now requires the logged-in user's assigned activity; normal completion no longer begins from a sudo recordset; public activity completion methods are guarded too.
- Fixed Odoo 19 PR search crash when relational purchase-order search is optimized to `any` / `any!`.

# Changelog

## 19.0.0.7.0

- Fixed Reset-to-Draft delivery at the mail-thread level, not only by filtering `partner_ids`.
- Requester and RFQ Link reset messages now use Odoo 19 `message_notify()` with `notify_skip_followers=True`, `notify_author=False`, and `notify_author_mention=False`.
- Reset actor is defensively removed from the explicit recipient recordset before direct notification creation.
- Reset request/completion chatter entries are audit-only (`notify_skip_followers=True`) and do not email followers.
- Suppressed automatic tracked-field mail during internal reset state writes (`mail_notrack=True`); the explicit reset audit note is the authoritative history.
- Immediate resets now log only the completed reset audit entry; the separate **Reset to Draft requested** audit entry is kept only when confirmed PO blockers create a real pending reset.
- Role-specific reset notifications are `user_notification` messages and no longer appear as two duplicate chatter posts authored by the reset actor.
- Added a regression case where the reset actor is both a Finance Approver and a PR follower; the actor must have zero `mail.notification` rows for the requester/RFQ-Link messages.
- Updated README, workflow, technical, troubleshooting, upgrade, validation, and test-plan documentation.

## 19.0.0.6.0

- Corrected **Reset to Draft** notification routing.
- The amendment/resubmission notification is sent only to the PR `requester_id`, except when that requester is the user who performed the reset.
- The linked-RFQ review notification is sent only to users configured in **Approval Setup → RFQ Link** (`link_user_ids`). RFQ `user_id`/responsible users are no longer added automatically.
- The user who performs the reset is excluded from both directed reset notifications and from the **Requisition Review** activity. The reset actor remains recorded in chatter for audit history.
- Added regression tests for requester routing, RFQ Link routing, RFQ responsible-user exclusion, and self-reset suppression.
- Updated workflow, technical, configuration, upgrade, validation, and UAT documentation for the notification matrix.

## 19.0.0.5.0

- Fixed **Attach Existing RFQ** so existing RFQ lines are preserved.
- Attaching a PR now appends that PR's material sections/notes/product lines to the selected unconfirmed RFQ.
- Kept document-level PR ↔ RFQ linkage only; no PR-line traceability or quantity matching was reintroduced.
- Documented and validated the three supported flows: Normal PR, Sale Order PR with **Confirm Sale Order**, and Office Supply PR.

## 19.0.0.4.0

- Removed PR-line ↔ RFQ/PO-line traceability fields and sync-key logic.
- Removed RFQ allocation matching, quantity reconciliation, partial-procurement indicators, and over-purchase checks.
- Removed Allocation Pending and Partial UI elements/filters/quantity columns.
- Added **Attach Existing RFQ** wizard for document-level linking to same-company unconfirmed RFQs only.
- Attaching a PR no longer creates or synchronizes RFQ lines.
- Allowed multiple PRs to share one RFQ using header-level links.
- PR completion now follows linked confirmed PO document state without quantity matching.

## 19.0.0.3.4

- Reset to Draft remains available to all authorized lifecycle stakeholders (requester, Manager, RFQ Create, SCM Approver, Finance Approver, PO Issuer and administrators).
- The original PR requester/submitter is now always notified when the PR actually reaches Draft, regardless of who performed the reset.
- A PR Workflow activity named **Requisition Review** is assigned to the requester after every completed reset so the amendment/resubmission action cannot be missed.
- Chatter continues to record every reset with the user who completed it, previous stage and reset reason; if a different user requested the reset, that initiator is also shown.
- For resets blocked by confirmed POs, the reset initiator now receives the **Complete Reset to Draft** activity once all blocking POs are Draft. The requester remains an allowed fallback completer.
- Remaining post-reset wording was aligned to **Send for Approval** instead of **Send to SCM / sending for SCM approval**.


## 19.0.0.3.3

- Notify the requester/submitter whenever a PR is actually returned to **Draft** through Reset to Draft.
- Notify the requester when a Manager uses **Send Back** from Submitted to Draft, including who sent it back and the Special Instruction note.
- Renamed the post-reset RFQ action from **Send to SCM** to **Send for Approval**; SCM approval activities are still created only after RFQ Create review is complete.
- Updated the RFQ review activity/chatter wording to match **Send for Approval** and remove the confusing implication that the PR was not already in the SCM/RFQ stage.
- Fixed the Reset/Cancel reason wizard when the note is empty: it now shows a normal **Please enter a reason before confirming** validation instead of an `Expected singleton` RPC traceback.
- Added regression coverage/documentation for empty-reason validation and Draft-return notifications.

## 19.0.0.3.2

- Removed visible Manager/Finance **Refuse** buttons; controlled **Cancel** is the single rejection/cancellation path.
- Enabled **Reset to Draft** from Canceled PRs for authorized stakeholders.
- Fixed Reset chatter HTML rendering and added **Reset by** (plus original requester when different).
- Reset notifications now explicitly include the user who reset the PR and always include configured RFQ Create users for linked RFQs.
- Added a post-reset **RFQ REVIEW** gate: linked RFQs no longer bypass RFQ Create users and go directly to SCM after resubmission.
- Added **Send to SCM** for RFQ Create users after they review synchronized linked RFQs; SCM activities are created only afterward.
- Kept the old Review behavior but renamed the UI action to **Send Back** to distinguish one-stage correction from Reset to Draft.
- Reordered form header actions so the primary workflow action appears before Reset/Cancel; existing RFQs expose secondary **Create Additional RFQ**.
- Moved the form `<header>` outside `<sheet>` so Odoo ribbons are anchored correctly below the statusbar and no longer overlap the header.
- Added **RFQ REVIEW** ribbon/filter and regression tests/documentation for the revised workflow.

## 19.0.0.3.1

- Replaced the stored `mail.activity.pr_workflow_activity` Boolean with a dedicated model-specific **PR Workflow** activity type.
- Prevents registry-wide `mail.activity` read failures when code is deployed before a database module upgrade.
- Added migrations for both databases that did not complete 19.0.0.3.0 and databases that already used the old Boolean marker.
- Reset/cancel still closes PR-generated workflow activities only; unrelated manual To-Dos remain untouched.

## 19.0.0.3.0

- Added controlled Reset to Draft with confirmed-PO dependency handling.
- Added dependency-aware PR cancellation and stakeholder notifications.
- Added PR-line ↔ purchase-order-line traceability and stable sync keys.
- Added split RFQ quantity allocation validation and over-purchase protection.
- Reworked Done so full confirmed quantity coverage is required.
- Added PARTIAL, RESET REQUESTED, CANCEL REQUESTED, ALLOCATION PENDING and OFFICE SUPPLY ribbons.
- Added amendment synchronization without changing purchase prices.
- Added native Odoo Alternative RFQ propagation (Create Alternative and Link Existing) and competitive-group quantity logic.
- Disabled standard RFQ Merge for PR-linked RFQs to protect PR-line traceability.
- Added Office Supply reset/resubmit and cancellation compatibility.
- Added Odoo-style PR and PO/RFQ search options.
- Kept cancelled RFQs/POs visible in PR history.
- Added stakeholder access retention after activities are completed.
- Marked PR workflow activities so reset/cancel preserves unrelated manual To-Dos.
- Added Office Supply guards for already-cancelled source requests and shared-PO reset warnings.
- Added upgrade migration, automated lifecycle tests and full functional/technical/UAT documentation.
