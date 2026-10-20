# Document Types

## Master model

`supplier.document.type` is the central master. Its fields are `name`, `sequence`, `active`, `sale_ok`, `purchase_ok`, `vendor_ok`, and `customer_ok`. Records are ordered by sequence then name.

| Flag | Label | Actual current usage |
|---|---|---|
| `sale_ok` | Sales | Controls types selectable on Sale Orders. |
| `purchase_ok` | Purchase | Controls types selectable on Purchase Orders. |
| `vendor_ok` | Vendor | Controls types selectable on Vendor Contacts. |
| `customer_ok` | Customer | Exists on the master but is not consumed by a model, view, or domain in this module. |

The **Customer Documents** label on the Sale Order is only a UI label. Its type domain is `sale_ok = True`, not `customer_ok = True`.

## Placement matrix

| Business area | Document model | Type filter | UI location |
|---|---|---|---|
| Vendor Contact | `vendor.document` | `vendor_ok = True`, `active = True` | Vendor Documents tab |
| Purchase Order | `purchase.supplier.document` | `purchase_ok = True`, `active = True` | Supplier Documents tab |
| Sale Order | `sale.supplier.document` | `sale_ok = True`, `active = True` | Customer Documents tab |
| Customer Contact | — | `customer_ok` not currently consumed | Not implemented in this module |

Inactive types are excluded from all three implemented selectors. The Vendor selector also provides defaults when creating a type from the field: Vendor enabled, Sales and Purchase disabled.

## Menu

The **Document Types** action is a single menu item whose XML parent is `base.menu_custom`. The parent’s rendered label depends on the database/environment configuration, so this module does not establish a reliable functional path such as Purchase → Configuration. The menu itself has no module-defined `groups` restriction; normal parent-menu visibility and model ACLs still apply.

See [the master model](../models/supplier_document_type.py) and [its views/menu definition](../views/supplier_document_type_views.xml).
