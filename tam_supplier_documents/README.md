# TAM Documents Type for Sale & Purchase

| Item | Value |
|---|---|
| Display name | TAM Documents Type for Sale & Purchase |
| Technical name | `tam_supplier_documents` |
| Odoo version | 19.0.0.0.0 |

## Purpose

This module centralizes Document Types and enables document uploads in supported Vendor, Purchase Order, and Sale Order areas. A Document Type's usage checkboxes decide where that type is eligible for selection.

```text
Document Type
    ↓
Usage Checkboxes
    ↓
Sales / Purchase / Vendor / Customer
    ↓
Eligible type appears in its implemented document selector
```

## What is implemented

- `sale_ok` controls types selectable on Sale Orders, on a tab labelled **Customer Documents**.
- `purchase_ok` controls types selectable on Purchase Orders.
- `vendor_ok` controls types selectable on Vendor Contacts.
- `customer_ok` exists on the Document Type master, but no separate Customer Document implementation using it was found in this module.

Vendor documents can carry expiry data and create reminder activities. They can also block Purchase Order confirmation when expired or due within 30 days. Purchase documents can be copied into a Sale Order through an interactive onchange when related Purchase Orders are selected.

This module is used by `tam_service_provider_creation_approval` for vendor-document onboarding/synchronization, but does not implement the onboarding workflow.

See [Document Types](docs/DOCUMENT_TYPES.md), [Workflow](docs/WORKFLOW.md), [Expiry Control](docs/EXPIRY_CONTROL.md), [Configuration](docs/CONFIGURATION.md), [Technical reference](docs/TECHNICAL.md), [Security](docs/SECURITY.md), and [manual test cases](docs/TEST_CASES.md).
