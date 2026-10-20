# Security

## Model ACLs

The module ACL CSV grants all permissions below to internal users (`base.group_user`).

| Model | Group | Read | Write | Create | Delete |
|---|---|---:|---:|---:|---:|
| `supplier.document.type` | `base.group_user` | Yes | Yes | Yes | Yes |
| `sale.supplier.document` | `base.group_user` | Yes | Yes | Yes | Yes |
| `purchase.supplier.document` | `base.group_user` | Yes | Yes | Yes | Yes |
| `vendor.document` | `base.group_user` | Yes | Yes | Yes | Yes |

## Menus and record rules

The Document Types menu has no `groups` attribute in this module. Visibility can still be affected by its `base.menu_custom` parent and standard Odoo access behavior, but this module adds no menu-group restriction.

No module-specific record-rule XML file or record-rule definitions were found. The module itself therefore adds no record-level filtering beyond Odoo defaults and any rules supplied by other installed modules.
