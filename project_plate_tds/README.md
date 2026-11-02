# Project Plate TDS — 19.0.1.3.0

Odoo 19 custom module for generating Plate TDS from artwork tasks.

## Changes in this version

- Removed obsolete RFQ methods, activity notifications, purchase-order link and redundant supplier/PR fields. Existing purchase orders, if any, are not modified.
- FG Width / Length: for Bag, `gdn_id.width` and `gdn_id.length`; for Roll, `gdn_id.source_line_id.req_coil_width_mm` and `gdn_id.source_line_id.req_cutoff_length_mm`. Dimensions are non-stored computed fields and available on both Bag and Roll forms/PDFs.
- Film Width: `sale_line_id.job_film_size_to_be_used` (fallback `gdn_id.source_line_id`), converted from numeric text or number with optional `mm` suffix. Non-numeric/composite values become 0.00; check the source if so.
- Plate and Production Layout attachments are selected/uploaded manually on TDS, and no longer copied from GDN when TDS is generated. Previously attached files are not deleted.
- Removed references in PDF/form to undefined `supplier_code` and `pr_rfq` fields; header retains supplier name, document/GDN references.
- Removed unsupported field `tracking=True` flags on `plate.tds.line` (line changes continue to be logged by the existing write override).

## Installation

Extract `project_plate_tds` to your addons directory, restart Odoo, upgrade module via Apps. Review an existing Bag and Roll GDN in staging and verify generated PDF.

## Notes

This archive did not include the live `crm_requirement_form` module; mapping is based on the previously provided source (`req_coil_width_mm`, `req_cutoff_length_mm`, `job_film_size_to_be_used`). Verify those fields still exist in deployed source. A fresh Odoo 19 install was not executed.
