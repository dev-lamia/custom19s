# Expiry control

Vendor Documents (`vendor.document`) can have `expiry_date`, `department_id` (Notify Department), `stop_notifications`, and `last_notified_on`. The module implements two separate expiry behaviors: reminder activities and Purchase Order confirmation blocking.

## Daily expiry reminder

The scheduled action **Vendor Document Expiry Reminder (30 Days) - Partner** runs `ResPartner.cron_notify_vendor_docs_expiry_30_days()` every day.

Its search domain is:

```text
today <= expiry_date <= today + 30 days
stop_notifications = False
```

It deliberately does not search documents already expired. For each matching document, it skips a document already notified today, then schedules a To-Do activity on the Vendor Contact for the Notify Department’s manager user:

```text
Vendor Document
    ↓
Notify Department
    ↓
Department Manager
    ↓
Manager's Odoo User
    ↓
To-Do Activity on Vendor Contact
```

No activity is created if the standard To-Do activity type, the vendor, the department, the department manager, or the manager’s Odoo user is missing. `last_notified_on` is only set after an activity is scheduled. It prevents duplicate activities on the same day, not reminders overall: a document still inside the date window may receive another activity when the daily cron runs on a later date.

`stop_notifications` only excludes a document from this reminder search. It is not considered by the Purchase Order blocking computation.

## Purchase confirmation block

`ResPartner._compute_expired_vendor_document_types()` computes `expired_vendor_document_type_ids` and `expired_vendor_document_type_names` from Vendor Documents with a non-empty date where:

```text
expiry_date <= today + 30 days
```

There is no lower date bound. Consequently it includes already-expired documents, documents expiring today, and documents expiring during the next 30 days. Documents with no expiry date are not included. The `expired_` field name is therefore broader than literal expiry: it also covers soon-to-expire documents.

On Purchase Orders, the related values hide the two Confirm controls and show a warning listing affected type names. Independently, `PurchaseOrder.button_confirm()` checks the same related type set and raises a `UserError`, so bypassing or not seeing the UI control does not allow confirmation.

| Behavior | Date rule | Includes already expired? |
|---|---|---|
| Expiry reminder cron | Today through Today + 30 | No |
| Purchase confirmation block | Expiry ≤ Today + 30 | Yes |

The confirmation block is based on the vendor's documents, not the Purchase Order's own Supplier Documents. Neither `stop_notifications` nor department/manager availability bypasses the block.
