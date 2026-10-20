# Changelog — CRM Requirement Form (Odoo 19)

> This file is maintained with the module. Dates are ISO 8601. Feature implementation dates are **not inferred** from documentation dates or ZIP/file timestamps.

## [Unreleased] — Documentation Updated: 2026-10-20

### [Changed] — Rename Job Code document label (2026-10-20)
- [2026-10-20] In Job Code → Quality Department, renamed the visible **Job Code Documents** section heading and upload field/button label to **Quality Documents**. The technical field `job_quality_attachment_ids`, stored files, permissions, upload behavior, and Requirement Form/GDN isolation are unchanged; updated README to match.


### [Changed] — Job Code Quality Department: independent file uploads (2026-10-20)
- [2026-10-20] Replaced the Job Code **Design Documents** line list in **Quality Department** with a simple **Job Code Documents** multi-file upload field (`many2many_binary`). Removed Document Type dropdown, category rows and Add a line list from **Job Code only**.
- [2026-10-20] New Job Code files use a dedicated `sale.order.line.job_quality_attachment_ids` Many2many attachment relation, exposed as `sale.job.code.configuration.job_quality_attachment_ids` and saved via the existing SQL-view `write()` forwarding. Nothing is fetched from or sent to Requirement Form / Product Specification / GDN document lines.
- [2026-10-20] Disabled Job Code document link auto-population on Sale Order confirmation/line write and Requirement Design document create/write; removed its upgrade backfill from the manifest. Retained the legacy line model/table and migration source file without running the migration, to preserve historical data. Requirement Form ↔ GDN document behavior is unchanged.
- [2026-10-20] Updated README technical mapping, deployment notes and proposed tests. ZIP/XML/Python static checks only; Odoo runtime testing has not been performed.

### [Superseded] — Previous Job Code Document Type rows (2026-10-20)
- [2026-10-20] Job Code → Quality Department → Design Documents now uses its own `sale.job.code.document.line` row model, analogous to GDN's `sale.gdn.document.line`. `document_type_id` remains a Many2one to the existing `crm.requirement.document.type` master, with explicit empty domain `[]` on Job Code's inline list; active configured types are available without an empty `id in []` restriction.
- [2026-10-20] Added `models/job_code_document_line.py` and `sale.order.line.job_code_document_line_ids`. Job Code's SQL-view model uses a non-stored `job_document_line_ids` related One2many and routes write commands to its Sale Order Line. The new table stores only Sale Order Line ↔ source Product Specification document relationships; type names and uploaded attachments are live related fields on existing source document rows (no duplicate file storage).
- [2026-10-20] Added idempotent backfill for existing Job Codes (`data/job_code_document_migration.xml`), source-document creation hook and Sale Order confirmation linking. Existing Product Specification and GDN source-file synchronization is retained; duplicate-copy specifications remain read-only. Changed the manifest, ACL, model imports, Job Code view and relevant models; no changes to GDN document view, GSM/production fields or the Job Code SQL SELECT.
- [2026-10-20] Updated README technical field mapping, upgrade instructions and proposed manual checks. Python/XML/archive static verification only; Odoo runtime testing pending.


### [Changed] — GDN Documents: manual Add a line, no empty defaults (2026-10-20)
- [2026-10-20] Stopped automatic creation of six **empty** GDN Document Type rows on new GDNs or subsequent REQ→GDN sync (`models/sale_order.py`, `sale.gdn.configuration._sync_document_lines`). GDN Documents remains an inline **Add a line** table with the same configured Document Type dropdown and multi-file uploads; `views/gdn_configuration_views.xml` is unchanged.
- [2026-10-20] On module upgrade, `_bootstrap_existing_gdn_document_lines()` now prunes only the old empty, non-source-linked standard-category placeholders. Existing uploaded GDN files, Requirement Form-sourced files, legacy attachment fields and custom document rows remain intact and synchronized; categories with real legacy/source files are still created as needed.
- [2026-10-20] Preserved the six configured Document Type **master options** and their dropdown selection (they are no longer six mandatory blank GDN rows). Updated `README.md` with the precise distinction, upgrade behavior and proposed QA-23 through QA-26. Python syntax and archive integrity checked; live Odoo runtime not tested.


### [Superseded] — Previous linked Job Code Design Documents (2026-10-20)
- [2026-10-20] Added a **Design Documents** section immediately below the existing GSM inputs in **Sales → Configuration → Job Code Configurations → Quality Department** (`views/gdn_configuration_views.xml`). Mirrors the Product Specification document list, including Document Type, multi-file Documents, sequence and inline **Add a line** editing.
- [2026-10-20] Introduced non-stored, live-linked `sale.job.code.configuration.design_document_line_ids` pointing to `requirement_specification_id.design_document_line_ids` (`models/job_code_configuration.py`). The SQL-view-backed Job Code `write()` forwards document commands to the source Product Specification. Existing `crm.requirement.design.document.line` hooks keep REQ → GDN documents synchronized; no duplicate stored document records or Job Code SQL columns were introduced.
- [2026-10-20] Preserved read-only document behavior for duplicate-copy Product Specifications using `job_design_documents_readonly`. Hide the section for jobs without a linked Product Specification. No changes to GSM fields, existing production, pouch/roll, GDN, REQ, security, manifest, or document synchronization code.
- [2026-10-20] Updated `README.md` with exact mapping, view behavior, upgrade and proposed QA steps. Static source checks only; live Odoo runtime not tested.

### [Changed] — GDN Source Sale Order Line form visibility (2026-10-19)
- [2026-10-19] Removed **Source Sale Order Line** (`source_line_id`) from the **GDN Configuration → Source & Traceability** form (`views/gdn_configuration_views.xml`, record `sale_gdn_configuration_form_view`). The GDN model field, optional list-view column, stored links, data synchronization and other form fields are preserved. This is a UI-only change; upgrade the module to apply the view update.
- [2026-10-19] Updated `README.md` with the GDN form visibility rule, deployment guidance and proposed QA-22. No Python/JS/SQL/security changes or live runtime test were made.

### [Added] — Job Code Bag/Pouch Details (2026-10-19)
- [2026-10-19] Added a **Pouch Details** tab (`job_pouch_details_tab`) in **Sales → Configuration → Job Code Configurations**, shown only when `fg_type == 'bag'`; Roll jobs retain the existing Roll Details layout. `views/gdn_configuration_views.xml` shows four fields: **Bag Length (mm)**, **Bag Width (mm)**, **Side Gusset (mm)** and **Bottom Gusset (mm)**.
- [2026-10-19] **Bag Length/Width** reuse existing read-only `sale.job.code.configuration.length` / `.width` SQL fields sourced from `sale.order.line.req_length` and `.req_width`; no duplicate length/width storage was introduced.
- [2026-10-19] Added editable `sale.order.line.job_pouch_side_gusset` and `job_pouch_bottom_gusset` (`fields.Float`, `copy=False`) in `models/sale_order.py`. Added corresponding SQL-view fields/SELECT aliases and permitted `write()` forwarding to `source_line_id` in `models/job_code_configuration.py`. These values are manual Sale Order Line data, not the pre-existing GDN `gusset` field. Module **upgrade** is required to create the underlying columns and rebuild the SQL view.

### [Changed] — Job Code Product Summary and GDN tab label (2026-10-19)
- [2026-10-19] Removed the redundant **Sale Product** (`product_id`) row **only from the Job Code Product Summary form**. Existing **Product** (`bag_type_product_tmpl_id`), Job Code SQL field, list view and other summary fields are preserved.
- [2026-10-19] Renamed the GDN form tab and its section heading from **Quantity & Dimensions** to **Dimensions** in `views/gdn_configuration_views.xml`. The page name `gdn_quantity_dimensions_tab`, underlying fields, Bag/Roll conditional visibility, and existing business rules are unchanged.

### [Docs] — Pouch Details and GDN Dimensions (2026-10-19)
- [2026-10-19] Expanded `README.md` with updated feature inventory, visibility/write restrictions, exact field-to-source mapping, SQL-view persistence, Product Summary cleanup, GDN label rename, synchronization notes, deployment steps and proposed QA-15 through QA-21.
- [2026-10-19] Updated `CHANGELOG.md` to record these changes with verified file/model references. **This documentation packaging pass changes only `README.md` and `CHANGELOG.md`; the existing functional patch is retained unchanged.** Source review and static archive checks only; live Odoo installation/upgrade not tested.

### [Changed] — GDN form Quantity & Dimensions display (2026-10-19)
- [2026-10-19] Removed only **Quantity** (`quantity`) and **Quantity UOM** (`quantity_uom_id`) from the GDN form's Quantity & Dimensions tab (`views/gdn_configuration_views.xml`); retained the underlying fields, GDN list columns, Total Thickness, Bag/Roll dimensions and all existing behavior.
- [2026-10-19] Updated `README.md` and `CHANGELOG.md` to reflect this UI-only change. XML syntax and ZIP integrity checked; Odoo runtime testing not performed.


### [Added] — Job Code Measuring Unit dropdown (2026-10-19)
- [2026-10-19] Added optional **Measuring Unit** (`job_measuring_unit_id`, `Many2one('uom.uom')`) immediately above **Process Sequence** in Job Code → Production Process. Choices are the existing Inventory → Configuration → Units & Packagings records; no new UoM options or menus were created.
- [2026-10-19] Persisted job-specific selection in existing `sale.job.code.repeat.size` storage (`measuring_unit_id`), projected by the Job Code SQL view (`LEFT JOIN repeat_cfg`). Extended the existing `write()` forwarding without adding a column to `sale.order.line` or affecting existing One Repeat Size. Deploy and upgrade the module to create the storage column and rebuild the SQL view.
- [2026-10-19] Updated `README.md` and `CHANGELOG.md`, including proposed non-executed QA. Python/XML and ZIP checks passed; Odoo runtime was not tested.

### [Changed] — GDN Documents UI (2026-10-19)
- [2026-10-19] Removed only the instructional helper text above GDN Documents line view. Kept editable document rows, attachments, configuration options and REQ synchronization unchanged (`views/gdn_configuration_views.xml`).
- [2026-10-19] Updated `README.md` and `CHANGELOG.md`; no runtime Odoo test performed.

### [Added] — Job Code GDN Color Details and Print Type (2026-10-19)
- [2026-10-19] Added **Color Details** (`gdn_color_details`, Integer related to `gdn_configuration_id.no_of_colors`) and **Print Type** (`gdn_print_type_id`, Many2one related to `gdn_configuration_id.print_type_id`) to Job Code → Product Summary. Both fields are read-only, live and visible for both Roll and Bag/Pouch FG types; edits remain on the GDN.
- [2026-10-19] Both fields are explicitly non-stored (`store=False`) on the `sale.job.code.configuration` SQL-view model: no new SQL columns, migration or stored Sale Order Line fields. Changed only `models/job_code_configuration.py` and `views/gdn_configuration_views.xml` plus `README.md` / `CHANGELOG.md`; other functionality unchanged. Static checks performed; Odoo runtime validation pending.

### [Fixed] — ZIP file access permissions (2026-10-18)
- [2026-10-18] Corrected ZIP mode `0600` to `0644` on `models/requirement_document_type.py`, `data/requirement_document_type_data.xml`, `data/requirement_document_type_migration.xml`, `README.md` and `CHANGELOG.md`. Prevents module import failures when Odoo runs as a non-owner inside Docker and the ZIP is extracted with stored Unix permissions.
- [2026-10-18] Module Python, XML, JS, security, manifest, database structures and functional behavior unchanged; updated `README.md` and `CHANGELOG.md` for troubleshooting. Live Docker/Odoo server validation pending.


### [Added] — Job Code Roll Details tab (2026-10-18)
- [2026-10-18] Added **Roll Details** tab to **Sales → Configuration → Job Code Configurations**, shown only for `fg_type == 'roll'`. Displays nine existing, read-only roll values (Coil Width, Cutoff Length, Final Roll Direction, Final Roll Weight, Final Roll OD, Final Roll Meters, Core ID, Core Thickness and Core Type) sourced through the existing `sale.job.code.configuration` SQL view from the linked Sale Order Line.
- [2026-10-18] Only `views/gdn_configuration_views.xml`, `README.md` and `CHANGELOG.md` are updated; no model/schema changes, manual production-process changes or GDN Roll Details changes. Odoo runtime validation pending.


### [Updated] — Document Types configuration and inline editing (2026-10-18)
- [2026-10-18] Replaced **Create Design Documents** popup with an inline editable One2many document list in Requirement Form → Product Specifications. Removed embedded document popup form; GDN Documents also uses inline list editing. Multi-file `many2many_binary` uploads remain supported per row (Odoo server testing pending).
- [2026-10-18] Added **Requirement Configuration → Document Types** master list (`crm.requirement.document.type`) with six default types, manager edit access, and shared selection dropdowns in Requirement Form and GDN. Disabled quick-creating categories from the row dropdown; new types are maintained in Configuration.
- [2026-10-18] Retained existing document line text fields for compatibility with existing GDN synchronization, added `document_type_id` for each document line, and an idempotent upgrade backfill that associates historical types/custom labels with configured records without dropping attachments.
- [2026-10-18] Updated `README.md` and `CHANGELOG.md`; executable changes are limited to document line models/views, configuration data/menu, manifest load entries, and related ACL/imports. Odoo staging runtime not verified.



### [Changed] — GDN Documents and manual design entries (2026-10-18)
- [2026-10-18] Replaced the read-only, related GDN Documents list with GDN-owned editable `sale.gdn.document.line` rows, supporting **Add a line**, free-text Document Type and multiple attachments per row; preserves REQ-to-GDN document import and synchronization without letting GDN uploads modify the original REQ.
- [2026-10-18] Automatically create six default GDN document types: Raw File, Customer Approved File, Digital Print File, Production Layout, Plate Layout and Color Separation. The module-upgrade data function backfills existing GDNs and brings historical categorized/uncategorized attachments into the new rows without deleting their original relations.
- [2026-10-18] Removed the **Existing Categorized GDN Documents** block from the GDN form; original legacy fields are retained in the model to protect existing integrations and stored files.
- [2026-10-18] Removed **Print Type** and **No of Colors** only from the Requirement Form Product Specifications view. GDN Design Information now uses independent, manually editable stored fields, not related writes into `sale.order.line`. Historical GDN display values are migrated once when present; Print Type configuration menu and other specification fields are unchanged.
- [2026-10-18] Updated source document row hooks and GDN source-file tracking to preserve direct GDN attachments when Requirement Form documents change. Added the GDN document-line ACL, model and upgrade data entry. Updated `README.md` and `CHANGELOG.md`; Odoo runtime test **not** performed.

### [Added]
- [2026-10-18] Introduced **Design Documents line view** on each Requirement Form Product Specification, supporting a free-text Document Type plus multiple uploaded files per row (`crm.requirement.design.document.line`, new model and access entry). GDN Documents now displays the linked design's document rows as a read-only, live related list. Previous six category attachment fields and existing file data are preserved and shown when populated. The new design-line model, `README.md` and `CHANGELOG.md` are included in the ZIP; requires module upgrade, not yet runtime-tested.
- [2026-10-18] GDN Configuration → Design Information: introduced optional editable alphanumeric **Print Direction** field (`sale.gdn.configuration.print_direction`, `fields.Char`) in `models/sale_order.py` and `views/gdn_configuration_views.xml`. Saved directly per GDN; no Requirement Form/Sale Order synchronization added.
- [2026-10-18] Job Code Configuration → Production Process: **One Repeat Size** is now a numeric `fields.Float` shown immediately before **No of Repeats** (`views/gdn_configuration_views.xml`). It is stored separately in new model `sale.job.code.repeat.size` (`models/job_code_configuration.py`), visible through a SQL-view `LEFT JOIN`. Existing One Up Size and No of Ups are unchanged.

### [Fixed]
- [2026-10-18] Resolved `psycopg2.errors.UndefinedColumn: column sale_order_line.job_one_repeat_size does not exist` by removing the ORM field and SQL view dependency on that missing Sale Order Line column. Repeat size now persists in a separate Job Code storage table.

### [Documentation]
- [2026-10-18] Updated `README.md` and `CHANGELOG.md` with corrected One Repeat Size location, numeric type, independent storage, migration instructions and proposed tests. Static validation completed; Odoo runtime verification pending.

### [Changed]
- [2026-10-18] [Fix] Replaced per-field Bag/Roll `invisible` expressions with two conditional `<group>` wrappers in `views/gdn_configuration_views.xml`. GDN Bag-only dimensions now belong to a Bag-only group (`fg_type != 'bag'`), while Roll-only Coil Width and Cutoff Length belong to a Roll-only group (`fg_type != 'roll'`). Quantity, UOM, and Total Thickness remain shared; stored field data and other tabs are untouched. Requires module upgrade on staging; no runtime verification performed.
- [2026-10-18] In **GDN Configuration → Quantity & Dimensions**, hide Bag-only **Length (mm)**, **Width (mm)** and **Gusset (mm)** when FG Type is Roll (`fg_type == 'roll'`). These values remain visible for Bag; Coil Width and Cutoff Length stay visible only for Roll. This is an Odoo 19 XML view visibility-only change.
- [2026-10-18] In **GDN Configuration → Quantity & Dimensions**, display **Coil Width (mm)** and **Cutoff Length (mm)** only when `fg_type == 'roll'`; remove those two fields from **Roll Details** to avoid duplicates. The two numeric values still come from related fields on the source Sale Order Line (`source_line_id.req_coil_width_mm` and `source_line_id.req_cutoff_length_mm`).
- [2026-10-18] Updated `views/gdn_configuration_views.xml` for layout/visibility only, and updated `README.md` and `CHANGELOG.md`. No models, business logic, manifest, security, or other views changed.

### [Docs]
- [2026-10-18] Added `README.md` with verified module metadata, navigation, features, models, workflows, configuration, sync mapping, security, installation, troubleshooting, and proposed QA scenarios.
- [2026-10-18] Added `CHANGELOG.md` to distinguish documented current source, historical upgrade-note evidence, and documentation-only modifications.
- [2026-10-18] Documented the already-present confirmed Sale Order **Select GDN clickable link** behavior, along with REQ Print Type, Roll Details, and GDN layer thickness field mapping.

### Scope
- **Current update (2026-10-18):** Display existing nine Roll values in the Job Code form when FG Type is Roll; presentation only. Existing Job Code SQL mapping and GDN values remain unchanged.
- **Latest update (2026-10-18):** corrected the Job Code One Repeat Size storage/type and its position before No of Repeats; removed the Sale Order Line missing-column dependency; updated model, view, ACL and documentation. GDN Print Direction and the prior GDN visibility fixes are unchanged.
- **Earlier same-day update (2026-10-18):** conditional Bag/Roll visibility adjustments in `views/gdn_configuration_views.xml`; retained in the current ZIP.
- **Previous same-day update:** moved Coil Width and Cutoff Length to Quantity & Dimensions (retained in this ZIP).
- **Earlier documentation-only update on 2026-10-18:** added README/CHANGELOG with no executable changes at that time.

## [19.0.0.0] — Release Date: Not verified

This is the **actual version string** in the supplied `__manifest__.py` (not a claimed new release). Baseline source inventory, reviewed on 2026-10-18:

### Verified present in supplied ZIP
- CRM Lead, Contact and Requirement Form integration; internal/public Requirement Form routes and Product Specifications.
- Configurable FG Types, Print Types (Surface and Reverse), Print and Finish, Features, Process Sequence and product category types.
- Sales GDN Configuration, GDN sequence generation/reuse and source traceability.
- GDN **Design Information**, conditional **Roll Details**, documents, and Layer 1–10 numeric Thickness (Microns) fields.
- Requirement Specification ↔ Sale Order Line/GDN synchronization paths and stored GDN snapshot logic.
- Job Code generation from confirmed Sale Order lines and Job Code SQL view.
- Sale Order Line `Select GDN` field: dropdown on quotations and clickable GDN record link after confirmation via `gdn_link_many2one` widget.
- Customer Ranking, Raw Material purchase Item Codes and inventory Item Code history.

**Runtime status:** Not tested as part of this documentation update.

## Historical notes preserved from the original module

The ZIP includes earlier `UPGRADE_NOTE*.txt` and `WHATSAPP_*.txt` documents. **Date: Not verified** for all historical implementation changes below. They are historical evidence, not proof that each statement still represents the current implementation or the current manifest version.

| Evidence file | Version mentioned by note | Documented historical topic | Implementation date |
| --- | --- | --- | --- |
| `WHATSAPP_SCHEMA_FIX.txt` | 19.0.0.1 | WhatsApp pre-migration field bootstrap | Not verified |
| `WHATSAPP_SCHEMA_FIX_V2.txt` | 19.0.0.2 | Earlier registry-bootstrap scenario | Not verified |
| `WHATSAPP_STUDIO_FIX.txt` | 19.0.0.3 | Existing Odoo Studio WhatsApp field placement compatibility | Not verified |
| `UPGRADE_NOTE_ITEM_CODE.txt` | 19.0.0.33 | Earlier raw material Item Code flow | Not verified |
| `UPGRADE_NOTE_ITEM_CODE_FIX.txt` | 19.0.0.34 | Earlier supplier-prefix schema fix | Not verified |
| `UPGRADE_NOTE_ITEM_CODE_LINE.txt` | 19.0.0.35 | Earlier PO-line Item Code logic | Not verified |
| `UPGRADE_NOTE_ITEM_CODE_INVENTORY_CONFIG.txt` | 19.0.0.36 | Item Code history configuration | Not verified |
| `UPGRADE_NOTE_REQ_SUMMARY*.txt` | Not specified | Requirement summaries, cards and manual entry notes | Not verified |
| `UPGRADE_NOTE_FEASIBILITY_GDN_FIX.txt` | Not specified | Repeat-job GDN persistence and feasibility filter note | Not verified |
| `UPGRADE_NOTE_VAT_SYNC.txt` | Not specified | VAT, Short Name, quotation and Incoterm synchronization note | Not verified |
| `UPGRADE_NOTE_JOB_CODE_PROCESS_FIELDS.txt` | Not specified | Job Code production process fields | Not verified |

There are no verified historical release dates in these notes. If confirmed Git tags or release records are supplied later, attach their dates here without inventing a timeline.

## Update policy

For every future ZIP update:
1. Verify the actual `__manifest__.py` version without changing it solely for documentation.
2. Add/refresh both `README.md` and `CHANGELOG.md` in the **module root**, inside the ZIP.
3. Document **only implemented/verified** changes, exact file/model references, and any tests actually executed.
4. Mark missing implementation/release dates as **Not verified**.
5. Preserve all unrelated code and archive entries.
