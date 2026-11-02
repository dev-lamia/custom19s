# Configuration and Troubleshooting — 19.0.0.7.1

## RFQ Create users

Configure RFQ Create users under **Purchase Requisition → Configuration → Approval**. These users can create an RFQ from a PR or attach an existing unconfirmed RFQ.

## Attach Existing RFQ does not show a purchase document

The selection intentionally allows only:

- same-company RFQs;
- state `draft`, `sent`, or `to approve`;
- RFQs not already linked to the current PR.

Confirmed/done/cancelled purchase documents cannot be newly attached.

## Existing RFQ lines disappeared

Version 19.0.0.7.0 appends PR lines using `Command.create` and does not replace the RFQ `order_line` collection. Upgrade the module to this version and retest. Existing lines should remain unchanged; the attached PR's material lines should appear after them.

## Can two PRs use one RFQ?

Yes. Multiple PRs can be attached to one RFQ. Every attachment adds the PR at document level and appends that PR's material lines as new RFQ lines. There is no PR-line ownership or quantity allocation logic.

## Sale Order PR is missing Confirm Sale Order stage

The stage appears only when `sale_order_id` is set on the PR. The field is populated either by selecting a Sale Order while the PR is still Draft or by clicking **Create PR** from the Sale Order. After Finance approval, such a PR must enter **Confirm Sale Order** before **Issue PO**.

## Reset notifications / actor sees messages

Version 19.0.0.7.0 separates reset audit history from directed notifications.

- The PR chatter contains the reset audit entry (`Reset by`, previous stage, reason). It is posted with follower notification disabled.
- PR review/amend/resubmit notification → PR `requester_id`, excluding the reset actor.
- Linked-RFQ review notification → Approval **RFQ Link** users only, excluding the reset actor.
- RFQ responsible user (`purchase.order.user_id`) → no automatic reset notification unless also configured in RFQ Link.
- A Finance/SCM/PO/RFQ user who performed the reset receives neither role notification merely because they follow the PR.

The role-specific messages use `message_notify(..., notify_skip_followers=True)`. They are direct `user_notification` messages and therefore do not appear as two extra visible chatter messages.

### Technical verification in Odoo shell

For a PR, inspect direct reset messages and actual notification recipients:

```python
pr = env['softeko.purchase.requisition'].search([('name', '=', 'TT/08/26-00071')], limit=1)
msgs = env['mail.message'].sudo().search([
    ('model', '=', pr._name),
    ('res_id', '=', pr.id),
    ('message_type', '=', 'user_notification'),
])
for msg in msgs:
    if 'reset to Draft' in (msg.body or '') or 'linked RFQ' in (msg.body or ''):
        print(msg.id, msg.subject, msg.partner_ids.mapped('name'))
        notifs = env['mail.notification'].sudo().search([('mail_message_id', '=', msg.id)])
        print('actual notifications:', notifs.mapped('res_partner_id.name'))
```

The reset actor should not appear in either the explicit `partner_ids` or the resulting `mail.notification` recipients for the two role messages.
