# Technical reference

## Dependencies

The manifest declares `sale_management`, `purchase`, `hr`, `mail`, and `contacts`.

- `sale_management` provides the Sale Order form extended with Customer Documents and related POs.
- `purchase` provides Purchase Orders, Supplier Documents, and confirmation interception.
- `hr` provides Notify Department and its manager.
- `mail` provides chatter/activity scheduling for expiry reminders.
- `contacts` provides the partner form extended with Vendor Documents.

## Models

| Model | Type | Purpose |
|---|---|---|
| [`supplier.document.type`](../models/supplier_document_type.py) | Custom | Central document-type master |
| [`vendor.document`](../models/vendor_document.py) | Custom | Documents stored against Vendor Contacts |
| [`purchase.supplier.document`](../models/purchase_supplier_document.py) | Custom | Documents stored against Purchase Orders |
| [`sale.supplier.document`](../models/sale_supplier_document.py) | Custom | Documents stored against Sale Orders |
| [`res.partner`](../models/res_partner.py) | Extended | Adds Vendor Documents and expiry status |
| [`purchase.order`](../models/purchase_supplier_document.py) | Extended | Adds Supplier Documents and confirmation block |
| [`sale.order`](../models/sale_supplier_document.py) | Extended | Adds sales documents and related-PO copying |

## Relationships

```text
res.partner
    │
    └── vendor.document
            │
            └── supplier.document.type
```

```text
purchase.order
    │
    └── purchase.supplier.document
            │
            └── supplier.document.type
```

```text
sale.order
    │
    └── sale.supplier.document
            │
            ├── supplier.document.type
            ├── source_po_id
            └── purchase_document_id
```

## Important methods

| Method | Input and logic | Output / side effect |
|---|---|---|
| [`SaleOrder._onchange_supplier_po_ids()`](../models/sale_supplier_document.py) | Related POs change; preserves manual lines, clears all lines, recreates manual lines, then rebuilds PO-derived lines while de-duplicating `(po.id, doc.id)`. | Replaces unsaved Sale Order document lines. |
| [`ResPartner.cron_notify_vendor_docs_expiry_30_days()`](../models/res_partner.py) | Daily search for non-stopped documents dated today through +30; resolves department manager user. | Schedules a To-Do activity on the vendor and sets `last_notified_on`. |
| [`ResPartner._compute_expired_vendor_document_types()`](../models/res_partner.py) | Reads Vendor Documents with an expiry date ≤ +30 days. | Computes blocked type IDs and comma-separated display names. |
| [`PurchaseOrder.button_confirm()`](../models/purchase_supplier_document.py) | Checks the vendor's computed blocked type IDs before standard confirmation. | Raises `UserError` when any exist, otherwise calls the standard confirmation. |

## Implementation notes and limitations

- `customer_ok` is a master-data field only here; no Customer Contact document model/tab/domain consumes it.
- Sales copying is onchange behavior, not persistent synchronization.
- The `expired_vendor_document_type_ids` name includes types that are merely due within 30 days, as well as expired types.
- `stop_notifications` suppresses reminder activities only; it does not alter the confirmation block.
- A missing expiry date means a Vendor Document is neither reminded about nor used for blocking.
- Without a department manager linked to an Odoo user, the reminder cannot be scheduled.
- `tam_service_provider_creation_approval` depends on this module and uses `vendor_ok` types for its approval documents; its onboarding and synchronization implementation is outside this module.
