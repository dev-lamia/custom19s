# Workflow

## Vendor Documents

On a partner with `supplier_rank > 0`, the **Vendor Documents** tab is visible. Each `vendor.document` belongs to that `res.partner` and records Document Type, Description, File, Expiry Date, Notify Department, Stop Notifications, and Last Notified On. The last field is read-only in the form.

Only active Document Types with `vendor_ok = True` can be selected. A document type is therefore configured first, then a user uploads the file and optionally supplies expiry/reminder information.

## Purchase Order Documents

Purchase Orders have a **Supplier Documents** tab backed by `purchase.supplier.document`:

```text
Purchase Order
    ↓
Supplier Documents
    ↓
Select eligible Document Type
    ↓
Upload file
```

The Type field accepts only active types where `purchase_ok = True`. Each line stores sequence, type, description, file, filename, and its parent Purchase Order.

## Sale Order Documents

Sale Orders have a **Customer Documents** tab backed by `sale.supplier.document`. Despite that label, the Type domain is active types where `sale_ok = True`; `customer_ok` does not participate.

Users can add a manual sale document directly. They can also choose one or more **Related Purchase Orders** (`supplier_po_ids`) to bring their Purchase Order documents into the sale order.

### PO-to-SO copy behavior

Changing `supplier_po_ids` triggers `SaleOrder._onchange_supplier_po_ids()`, which performs this UI-time rebuild:

```text
Existing Sale Order Documents
    ↓
Preserve manual lines (no Source PO)
    ↓
Clear all current lines
    ↓
Recreate manual lines
    ↓
Read documents from selected Purchase Orders
    ↓
Create PO-derived Sale Order lines
    ↓
Store Source PO + Source Purchase Document
```

PO-derived lines populate `source_po_id` and `purchase_document_id`. Manual lines are identified by having no `source_po_id`. During one rebuild, a set keyed by `(PO ID, Document ID)` avoids creating the same selected PO/document pair twice. There is no database-level uniqueness constraint in this module, and no continuous or background synchronization: later edits to the Purchase Order document do not automatically update an already-saved Sale Order.

If a related PO is removed, its generated lines disappear on the next onchange rebuild. Manual lines remain; selected-PO lines for still-selected POs are recreated from their current PO document values.

## Purchase confirmation protection

Before confirming a Purchase Order, the order checks the vendor’s computed affected Vendor Document Types. A warning and hidden Confirm buttons provide UI protection, while `button_confirm()` also raises a server-side `UserError`. See [Expiry Control](EXPIRY_CONTROL.md) for the date rule.
