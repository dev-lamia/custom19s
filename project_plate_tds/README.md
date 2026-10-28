# Project Plate Technical Data Sheet (Odoo 19)

A standalone addon that creates one Plate Technical Data Sheet per artwork `project.task`.
It uses the existing relation: `project.task.artwork_sale_order_line_id.gdn_configuration_id`.

## Install

1. Add the `project_plate_tds` directory to your Odoo addons path.
2. Update Apps List, then install **Project Plate Technical Data Sheet**.
3. In Settings > Users, grant the appropriate users **Plate TDS User** or **Plate TDS Manager**.
4. Open an Artwork Task linked to a Sale Order Line with an existing GDN.
5. Click **Generate TDS**, review values, fill in technical fields, then Save.
6. Reopen the saved document using the task's **Plate TDS** smart button.
7. Click **Print TDS** for a QWeb PDF report.

### Development shell

```bash
mkdir -p /path/to/custom_addons
unzip project_plate_tds.zip -d /path/to/custom_addons
./odoo-bin -d YOUR_DATABASE -u project_plate_tds --stop-after-init
```

## Data mapping

- Task → Sale Order Line: `artwork_sale_order_line_id`
- Sale Order Line → GDN: `gdn_configuration_id`
- Job code: `sale.order.line.job_code`
- GDN number: `sale.gdn.configuration.gdn_number`
- Customer: `sale.gdn.configuration.partner_id`
- Customer code: `res.partner.customer_code`
- Structure: layer 1–10 product template names joined in order
- Width, length, unclassified gusset: GDN fields `width`, `length`, `gusset`
- Print Type: GDN `print_finish_id.display_name` (provisional mapping — verify terminology)
- Pouch Type: GDN `bag_type_product_tmpl_id` or roll subtype
- Layouts: GDN `doc_plate_layout_ids` and `doc_production_layout_ids`

## Items requiring business decisions

- Source GDN's `gusset` does not distinguish side vs bottom: retain original in a reference field;
  enter `side_gusset` and `bottom_gusset` manually.
- No reliable source was identified for automatic print direction, shade reference, print count,
  bleed, ups, circumference, plate dimensions, ink grade or sleeve size. They remain editable.
- No calculation formula is assumed. Fill calculation values manually pending approval of formulas.
- PR/RFQ number is editable; user must confirm whether this should have a separate sequence.
- Image attachments can render in PDF. Other document types are shown by filename only.
- The module uses one TDS per artwork task (unique SQL constraint), and reopening Generate TDS
  opens existing record instead of creating duplicates.

## Verification

Python AST and XML parsing passed locally. Installation and end-to-end tests in a real Odoo 19
instance are still required. Specifically validate form inheritance, group permissions, GDN mapping,
layout visibility, QWeb rendering, and the report output against the supplied paper layout.

## Version 19.0.1.0.2 - Access changes

All Odoo internal users (`base.group_user`) now have full CRUD access to Plate TDS and plate lines. No separate Plate TDS roles are required. The Generate TDS button, smart button and menu have no custom group restriction. Portal/public users are intentionally excluded. Upgrade the module to apply changes. Previous group records may remain in the database but no longer gate access.

## v19.0.1.0.3 — Backend theme

Scoped Plate TDS form styling matching the GDN green hero, rounded panels, typography, and responsive spacing. No access-right changes.
