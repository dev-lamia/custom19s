# Technical Notes — 19.0.0.7.0

## Document-level relationship

`purchase.order.pr_requisition_ids` is the active many-to-many relationship between Purchase Requisitions and RFQs/POs. `pr_requisition_id` remains as a legacy single-link compatibility field.

No PR ownership/identity fields are added to `purchase.order.line`, and no sync/identity field is used on `softeko.purchase.requisition.line`.

## Attach Existing RFQ

`softeko.purchase.requisition.attach.rfq.wizard` accepts a same-company purchase document only while it is in `draft`, `sent`, or `to approve`.

`action_attach()` performs one `purchase.order.write()` containing:

- `Command.link(pr.id)` on `pr_requisition_ids`; and
- one or more `Command.create(...)` operations on `order_line`.

Only `Command.create` is used for RFQ order lines. The implementation deliberately does **not** use `Command.set`, `Command.clear`, or replacement commands on `order_line`, so pre-existing RFQ lines are preserved and the selected PR's material lines are appended.

The appended lines contain normal purchase line values only (sequence, display type/name or product, quantity, UoM, description, planned date). They contain no PR-line ownership metadata.

## Three workflow branches

The PR state model contains the Sale Order-specific `sale_order` state labelled **Confirm Sale Order**.

- Normal: `draft → submitted → rfq → finance_approved → po_issued → done`
- Sale Order: `draft → submitted → rfq → finance_approved → sale_order → po_issued → done`
- Office Supply: `draft → finance_approved → po_issued → done`

`action_fd_approve()` branches on `sale_order_id`. If a Sale Order exists, Finance sends the PR to `sale_order`; otherwise it goes directly to `po_issued`.

`sale.order.action_confirm()` calls the linked PR confirmation check, which moves PRs currently in `sale_order` to `po_issued` and creates the PO Issuer activity.

## Confirmation control

`purchase.order._validate_pr_confirmation_stage()` validates only PR workflow stage and pending reset/cancellation flags. It performs no product, UoM, line mapping, requested quantity, allocated quantity, or over-purchase checks.

## Reset notification routing

`softeko.purchase.requisition._perform_reset_to_draft()` separates audit logging from directed communication.

The reset audit entry is kept in chatter with `notify_skip_followers=True`, so it records the actor/stage/reason without emailing PR followers. Internal writes that set/clear reset flags and move the PR to Draft use `mail_notrack=True`, preventing tracked-field follower mail from becoming a second notification channel. Directed role messages are created through `_notify_users_direct()`, which uses Odoo 19 `message_notify()` with:

```python
notify_author=False
notify_author_mention=False
notify_skip_followers=True
```

Recipient construction is explicit:

```python
requester_recipient = self.requester_id.filtered(lambda u: u.id != reset_by.id)
rfq_users = cfg.link_user_ids.filtered(lambda u: not u.share and u.id != reset_by.id)
```

Rules:

1. Requester notification and **Requisition Review** activity use only `requester_id`.
2. RFQ-review notification uses only approval configuration `link_user_ids`.
3. `purchase.order.user_id` is not unioned into the RFQ-review recipient set.
4. `reset_by` is removed from both explicit recipient sets.
5. `notify_skip_followers=True` prevents Finance/SCM/other PR followers from being added by mail-thread follower logic.
6. The role messages are `mail.message` records with `message_type='user_notification'`; they are direct notifications and are not shown in the normal PR chatter stream.
7. The visible chatter audit message remains separate and is non-notifying.

This protects the routing rule at both levels: the actor is removed before message creation, and Odoo's follower expansion is disabled for the direct notification itself.
