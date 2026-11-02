# Current regression test plan — 19.0.0.8.8

The automated suite is intentionally aligned with the three live business flows and avoids old implementation-detail tests.

## Covered flows

1. **Normal PR**: Draft → Submitted to Manager → SCM Approval / RFQ Link → Finance Approval → Issue PO → Done.
2. **Sale Order PR**: Draft → Submitted to Manager → SCM Approval / RFQ Link → Finance Approval → Confirm Sale Order → Issue PO → Done.
3. **Office Supply PR**: Draft → Finance Approval → Issue PO → Done. Manager and SCM are intentionally bypassed.

## Reset to Draft coverage

- Requester reset from Submitted.
- Manager reset from Submitted.
- RFQ Create user reset while waiting for RFQ link.
- SCM Approver reset after an RFQ is linked.
- Finance Approver reset from Finance Approval.
- PO Issuer reset from Issue PO.
- Confirmed PO blocks reset until the PO is returned to Draft, then the reset initiator/requester can finalize.
- Existing RFQ stays linked and requires explicit RFQ review after reset/resubmit.
- Sale Order flow returns to the Sale Order stage after reset/resubmit/reapproval.
- Office Supply requester can reset from Finance without Purchase or Accounting access and resubmit directly to Finance.
- Finance can reset an Office Supply PR.
- Office Supply requester can reset from Issue PO before a PO exists.
- Office Supply Finance **Send Back** remains blocked.
- Non-stakeholders cannot reset/cancel.
- Manual To-Do activities survive reset; workflow activities are cleaned up.

## Cancellation coverage

- Immediate cancellation when no RFQ/PO dependency exists.
- Draft RFQ blocks cancellation until the RFQ is cancelled/unlinked.
- Confirmed PO blocks cancellation until the PO is cancelled.
- Sale Order flow cancellation respects the linked RFQ dependency.
- A normal cancelled PR can be reopened with Reset to Draft.
- A cancelled Office Supply PR is final and cannot be reopened.

## Run only this current suite

```bash
docker exec -it odoo_dev odoo -c /etc/odoo/odoo.conf -d 7-sep-test -u softeko_purchase_requisition --test-tags "pr_current_workflow" --stop-after-init --http-port=8079 --max-cron-threads=0
```

A clean run ends with `0 failed, 0 error(s)`.
