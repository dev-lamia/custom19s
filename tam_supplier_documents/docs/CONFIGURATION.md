# Configuration

## Create a Document Type

```text
Document Types
    ↓
Create type
    ↓
Set Name and optional Sequence
    ↓
Choose placement flags
    ↓
Sales / Purchase / Vendor / Customer
```

Keep the type active to make it selectable. Configure one or more actual placements as required:

| Flag | Functional placement in this module |
|---|---|
| Sales | Sale Order → Customer Documents; selected by `sale_ok` |
| Purchase | Purchase Order → Supplier Documents; selected by `purchase_ok` |
| Vendor | Vendor Contact → Vendor Documents; selected by `vendor_ok` |
| Customer | No functional placement currently uses `customer_ok` |

The Document Types menu is attached to `base.menu_custom`; its parent label can differ by environment. See [Document Types](DOCUMENT_TYPES.md).

## Configure Vendor expiry reminders

For a reminder activity to be created, all of the following must be true:

- The Vendor Document has an Expiry Date from today through the next 30 days.
- Notify Department is selected.
- That department has a manager.
- The manager is linked to an Odoo user.
- Stop Notifications is false.
- The daily **Vendor Document Expiry Reminder (30 Days) - Partner** cron is active.

The activity is created on the Vendor Contact and assigned to the department manager's user. `last_notified_on` avoids a second activity for the same document on the same date.

Expiry control and confirmation blocking are explained in [Expiry Control](EXPIRY_CONTROL.md); notably, blocking does not require a department and also includes already-expired documents.
