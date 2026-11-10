## [19.0.1.0.17] - 2026-11-10

### Added
- **Limit Type per TDS line:** `± % of Target` (0.5 / 1 / 2 / 3 / 4 / 5 / 10 %), `± Fixed amount`, `Fixed Min / Max`, `Minimum only`, `Maximum only`, `Visual / Manual`. Typing the Target fills Min/Max automatically; no checkbox or Calculate button. Workbook text is translated on load (57 of 66 master rows become numeric; compound/visual rows stay manual). Activation requires a Target on ± lines.
- **Catalog errors per test:** chosen on the TDS line (pre-filled from the master test, e.g. Thickness → RM001, Dyne → RM005). The inspector's dropdown shows only those errors (whole catalog when none chosen). An out-of-spec or failed reading cannot be saved without a Catalog Error.
- **Pending RM QC list** (Quality → Quality Control → Pending RM QC): receipts with QC-required material, with status Pending / In Progress / Failed / Passed and an *Inspect* button. Status badge also on the receipt form.
- **Automatic Pass:** when every required reading is entered and within range, the inspection passes by itself. Fail stays a manual decision.
- **Unit dropdown:** new `QC Units` master (Quality → Configuration → QC Units), created from the workbook units; new units can be typed in the dropdown.
- **Receipt validation gate:** a failed RM inspection (or an out-of-spec reading) blocks *Validate*. Unfinished RM QC also blocks *Validate*; the inspections are created automatically and opened. Set system parameter `quality_rm_spec_sampling.validate_requires_qc_pass` = `0` to allow validating before QC is finished (failed QC still blocks).
- Adding sample count in *Enter Results* adds the extra rows immediately.

### Fixed
- Batch numbers typed on a not-yet-validated receipt (`lot_name`) now create/reuse the lot and give one inspection per batch. An inspection created before the batch was typed is attached to the batch instead of duplicated.

### Upgrade
- Pre-migration keeps every existing numeric line numeric (as Fixed Min / Max with its stored limits); reference lines stay manual. Active standards and recorded results are not changed. Draft standards get automatic limit types and catalog errors.
- Native Quality menus and the approval behaviour are unchanged. Only the two new RM menus (Pending RM QC, QC Units) are added to the existing RM menu placement.

### Validation
- Python compile, XML parse and limit parsing against all 66 workbook rows checked offline. New runtime tests in `tests/test_limits_and_receipt_gate.py` must be run on an Odoo 19 staging database.

## [19.0.1.0.16] - 2026-11-09

### [Fixed]
- Made Quality App menu placement fail-safe with transaction savepoints: if the Quality navigation layout is unexpected, the old RM Quality menu remains available and the module upgrade does not abort solely due to this integration.
- Restores the original native Quality menu action and name **only if** it is still using the custom action from v14. Preserves unrelated menu/action edits.
- Places RM QC Specification and Quality Inspection under Quality > Quality Control when the Quality app is found; configuration menus stay under Quality > Configuration.
- Preserves the existing incoming RM duplicate-check guard, sampling, QC data, security and all non-menu business logic.

### [Validation]
- ZIP integrity, Python AST and XML syntax checked offline. Live Odoo install or 500 resolution cannot be confirmed without the current server traceback.

## [19.0.1.0.15] - 2026-11-09

### Fixed
- Avoided direct modification of native Quality Control Points / Quality Checks menu actions. Instead, hide only the native navigation menu records and show RM QC Specification / Quality Inspection under Quality -> Quality Control.
- Restore native menu action/name from 19.0.1.0.14's saved snapshots before hiding them on upgrade.
- Explicitly hide the old RM Quality app menu using supported ir.ui.menu XML record updates.
- Kept inspection, sampling, stock, manufacturing, permissions, master data and QC duplicate guard unchanged.

### Validation
- Python AST, XML parse, ZIP integrity verified. No live Odoo database/runtime test was performed.

## [19.0.1.0.14] - 2026-11-09

### [Changed] Single native Quality navigation
- [2026-11-09] Reused the **native Quality Control Points menu** for `RM QC Specification`. It now opens the existing `rm.qc.specification` list and full TDS/sampling form; no additional specification menu is shown.
- [2026-11-09] Reused the **native Quality Checks menu** as `Quality Inspection`, with this module's sampling/measurement inspection views. The action displays all `quality.check` records, including native checks; no second inspection menu is shown.
- [2026-11-09] Preserved the old addon menu XML IDs as inactive for upgrades; retained Quality → Configuration entries and no standalone RM Quality app.
- [2026-11-09] Added idempotent native-menu discovery without undocumented Enterprise XML IDs; native actions/labels are saved before being changed and restored on module uninstall.

### [Compatibility / Testing]
- [2026-11-09] **Did not merge** `quality.point` and `rm.qc.specification`: native QCP check-generation rules remain intact; existing RM specification records and Odoo quality checks are not migrated or deleted.
- [2026-11-09] No QC business validations, duplicate prevention, specification measurements, purchase or stock logic changed. Python/XML/ZIP static checks only; live Odoo 19 upgrade/uninstall tests not executed.

## [19.0.1.0.13] - 2026-11-09

### [Changed] Quality app navigation
- [2026-11-09] Reparented the existing `QC Standards (TDS)` and `QC Inspections` menu records under the installed **Quality → Quality Control** menu.
- [2026-11-09] Reparented `Test Templates`, `Defect Catalog`, `Product Properties`, and `Department Consumables` under **Quality → Configuration**.
- [2026-11-09] Deactivated the old standalone `RM Quality` and intermediate `Configuration` menus while preserving their XML IDs, all actions and existing records. The integration runs on **new installation and upgrade**.
- [2026-11-09] The menu resolver does not assume an undocumented Enterprise external ID; for nonstandard Quality menu layouts, missing subsections fall back to the existing Quality root (never a new app).

### [Compatibility / Testing]
- [2026-11-09] No QC inspection creation, sampling, specification, stock, purchase, security or approval logic changed. No historical QC entries were deleted.
- [2026-11-09] Python/XML and ZIP structure checked statically. Live Odoo 19 installation or upgrade not executed.

## [19.0.1.0.12] - 2026-11-09

### [Fixed]
- [2026-11-09] Receipt QC generation now checks for an existing `quality.check` by **receipt + product + lot**, regardless of which QC Standard was current when the original check was created. Repeated clicks or later standard revisions no longer generate a new RM inspection for the same receipt/product/lot.
- [2026-11-09] When an uncompleted native Quality Point check exists, the receipt QC button can reuse that check and load the RM sampling standard instead of creating a second check. If the only native check is completed, the user is instructed to review that check; the module does not overwrite it.
- [2026-11-09] A model-level constraint prevents creating a second specification-linked incoming RM inspection for the same receipt/product/lot, including manual creation through the form.

### [Tests / Data safety]
- [2026-11-09] Added proposed Odoo 19 regression tests covering repeated button clicks, QC Standard revision, duplicate manual creation, and reuse of a pending native check. Static Python checks completed; live Odoo execution not performed.
- [2026-11-09] Previous QC records, Completed/Passed/Failed states, sampling logs, and results remain unchanged. Historical duplicates require review; no automatic record deletion, merging or hiding.

## [19.0.1.0.11] - 2026-11-09

### [Changed] UI refresh (simpler, cleaner, easier to use)
- QC Standards: status/scope badges, Active/Archived ribbons, 3-step guide on drafts, product as the form title, lock notice, new **Create New Version** button on locked standards, kanban view grouped by status, search filters (Draft / Active / Incoming / Production / Archived) and grouping.
- QC Inspections: 3-step guide, per-test and overall **progress bars**, red/green test rows, **Enter Results** button turns into **View** when a test is complete, Pass/Fail ribbons, out-of-spec warning, `Load QC Tests` hidden once tests exist, kanban view grouped by status, filters (My Inspections / To Do / Passed / Failed) and grouping.
- Enter Results popup: allowed range at the top, plain-language hint (numeric vs by-eye), result badge, Pass/Fail column shown only for manual tests.
- Menus renamed in plain words and ordered by daily use: QC Standards (TDS), QC Inspections, Configuration (Test Templates, Defect Catalog, Product Properties, Department Consumables).
- Masters: search + group-by on all lists, inline-editable Defect Catalog, toggle switches for yes/no fields, friendly empty-list help text.
- Receipt button renamed **QC Inspection**.
- Added `static/src/css/rm_qc.css` (uses Bootstrap variables, so dark mode works) and a module icon.

### [Added] (display only, no migration needed)
- Non-stored computed fields: `rm.qc.inspection.parameter` (`expected_count`, `entered_count`, `failed_count`, `progress`) and `quality.check` (`rm_qc_progress`, `rm_qc_failed_count`).

### [Compatibility]
- No business logic, states, security rules, data or XML IDs were changed. Python and XML syntax and field references were statically checked; a live Odoo 19 upgrade was not run.

## [19.0.1.0.10] - 2026-11-03

### [Changed]
- [2026-11-03] Consolidated Product `QC Setup` and `RM Technical Properties` into one `RM Quality` tab; retained Configuration-driven Property values and QC Standards smart button.
- [2026-11-03] Removed the visible internal `Submit for QC Manager Approval` step. QC Standards can be activated directly from Draft by `action_approve` (renamed `Activate Standard` in UI). Existing DB state `approved` remains the technical key for compatibility, but is displayed as `Active`.
- [2026-11-03] Renamed PO/Receipt validation messages to describe an `Active QC Standard`, not built-in QC Manager approval.
- [2026-11-03] Simplified the QCS form to product details, QC Tests/Sampling table and notes; kept standard per-test drilldown.
- [2026-11-03] Product `RM Quality` tab is hidden for ordinary sale-only finished goods with no RM QC configuration.

### [Compatibility]
- [2026-11-03] Retained legacy `submitted` state value, `action_submit` compatibility method (now reports a deprecation notice), PR technical records, prior QC data, duplicate-to-draft and company restrictions. Did not remove database columns or old view IDs.
- [2026-11-03] External Dynamic Approval can be configured on `rm.qc.specification.action_approve`, but this addon does not integrate with or enforce that external module.
- [2026-11-03] Python and XML syntax, data cross-references and ZIP integrity checked; live Odoo 19 upgrade not performed.

## [19.0.1.0.9] - 2026-10-28

### Fixed
- [2026-10-28] Avoid deleting legacy parent `ir.ui.view` records during PR removal; other modules may inherit them through `inherit_id`.
- [2026-10-28] Hide legacy PR navigation while retaining PR model/view/action XML IDs for upgrade compatibility and historical data preservation.
- [2026-10-28] Preserve direct Purchase Order QC confirmation validation without changing Inspection logic.

### Migration
- [2026-10-28] Removed the destructive 19.0.1.0.8 pre-migration that unlinked PR UI records. PR database schema and records are intentionally not dropped.

## [19.0.1.0.8] - 2026-10-28

### [Removed]
- [2026-10-28] Removed this add-on's Purchase Requisition (PR) forms, models, menus, security rules, approval role, sequence and related RFQ creation action.

### [Changed]
- [2026-10-28] Preserved direct `purchase.order.button_confirm()` validation of approved incoming QC specification in its own `models/purchase_order.py`; existing QC Setup, receipt sampling, inspection and production QC are unchanged.
- [2026-10-28] Simplified RM Quality navigation to **1. QC Setup (Once)** and **2. Receipt QC Results** plus Master Data.
- [2026-10-28] Added upgrade cleanup for obsolete PR user-interface/security records. Back up existing `PRQ` data before upgrading; the removed model's historical records may not survive the upgrade.

### [Docs]
- [2026-10-28] Updated README to reflect direct Purchase RFQ/PO flow without this add-on's PR.

## [19.0.1.0.7] - 2026-10-28
### [Update]
- [2026-10-28] Made **More / Master Data → Product Property Configuration** the single source of technical product identification fields, maintained by RM Material Type with optional Default Unit and Active status.
- [2026-10-28] Removed the Product **Load Property Templates** button. Properties now appear automatically on new products / Material Type changes and are refreshed when master property definitions change.
- [2026-10-28] Existing products are synchronized on module upgrade. Unrelated or duplicate product property rows are **archived, not deleted**, preserving entered values; changing the material type back restores matching archived rows.
- [2026-10-28] Product operators enter only Property Value / Unit. Property names and the available fields are controlled in Configuration, not manually added to products. QC Specification / Purchase / Inspection logic unchanged.
- [2026-10-28] Static XML, Python and ZIP tests performed; live Odoo 19 upgrade execution remains unverified.

## [19.0.1.0.6] - 2026-10-28
### [Style]
- [2026-10-28] Replaced the lower Product form **Create QC Standard / TDS** button and embedded specification list with one standard **QC Standards** smart button in the upper Product button box.
- [2026-10-28] Smart button count reflects the product-linked QCS records (including archived records). Its linked action opens a product-filtered list; **New** creates a draft using the same product by default, with incoming scope.
- [2026-10-28] Retained existing QCS records, duplication, approvals, PR/PO gates and QC inspection logic unchanged. No automatic QCS creation from opening a product.
- [2026-10-28] Static syntax/XML/archive checks performed; Odoo 19 runtime view rendering/upgrade not verified.

## [19.0.1.0.5] - 2026-10-28
### [Update]
- [2026-10-28] Simplified the QC Specification screen: removed the user-facing Load Tests and Create New Version buttons. Selecting the product pre-fills applicable test parameters automatically for new draft specifications; new empty drafts also auto-fill on save.
- [2026-10-28] Kept Excel-requested duplication through the standard Odoo Action > Duplicate; copies always start as a new draft and require QC approval. Approval, sampling and inspection logic remain unchanged.
- [2026-10-28] Existing specification lines are preserved; no auto-population overwrites a populated saved draft.

## [19.0.1.0.4] - 2026-10-28

### [Changed]
- [2026-10-28] Simplified the existing Odoo Quality extension UI around QC Setup, Purchase Requests, and Receipt QC Results.
- [2026-10-28] Moved supplementary technical properties, inspection metadata, and approval details to secondary tabs; clarified inline instructions and button labels.
- [2026-10-28] Kept all model methods, business rules, approval checks, and prior data unchanged.

## [19.0.1.0.3] - 2026-10-28
### [Fix]
- [2026-10-28] Odoo administrators (Access Rights/Settings) may approve submitted RM/Consumable PRs without membership in the custom PR / GM Approver group. Ordinary users still require that group.
- [2026-10-28] Applied the same server-side authorization in both `action_approve()` and guarded `write()` on `rm.qc.purchase.request`; existing PR state validation, approved RM specification checks, company rules and RFQ restrictions remain unchanged.
- [2026-10-28] Python syntax and archive integrity checked; Odoo database upgrade/runtime approval testing not performed.

## [19.0.1.0.2] - 2026-10-28
### [Style]
- [2026-10-28] Reorganized Product RM QC into classification, technical identification and associated approved TDS sections, matching the source workbook.
- [2026-10-28] Replaced the wide specification editor with a concise TDS parameter overview and an expanded property-level editor for specification, numeric limits and sampling procedure.
- [2026-10-28] Simplified Quality Check / Inspection into receipt and batch information, approved TDS, and sampling measurements.
- [2026-10-28] Added direct **Enter Results** action from each test parameter to its Measurement Log popup.
- [2026-10-28] Simplified module menu labels; preserved existing menu/action IDs and existing ACL access.
### [Compatibility]
- [2026-10-28] Does not modify purchase approval, QCP, stock release, sample result evaluation or automatic Pass/Fail business logic; Odoo runtime upgrade verification remains pending.

# Changelog

## [Unreleased] - 2026-10-28

### [Update] — 2026-10-28 — Internal-user access temporarily opened
- All logged-in internal users (`base.group_user`), including Administrator, can read/create/edit/delete records in all 11 custom RM QC models. Public and portal users do not gain access.
- Exposed custom QC/TDS, approval, PR, identification, receipt/MO buttons and module menus to all internal users; enabled New on QC Master Parameter list.
- Allowed any internal user to execute the module's QC specification confirmation / archive and PR approval actions, without granting Odoo's native Purchase, Quality or Inventory permissions.
- Kept TDS state and revision locks, PR state validations, QC measurement checks, multi-company record rules and standard Odoo Purchase User requirement for creating an RFQ unchanged.
- This broad access is intended for temporary evaluation and should be restricted again before production use. Restricting visibility with a separate access manager does not itself undo these backend ACL changes.

### [Fix] — 2026-10-28
- Added **read-only** ACLs for internal users on QC data embedded in standard Product and Quality Check forms (product identification, specification/lines, QC references and inspection logs). Prevents Access Error on `product.template.rm_qc_identification_line_ids` for users without the custom RM QC group. Existing QC Inspector/Controller/Manager edit rights and company rules are unchanged. No public/portal access granted.

### [Fix] — 2026-10-28
- Updated Odoo 19 lot handling from `quality.check.lot_id` to `quality.check.lot_ids` for computed batch references, receipt QC check creation, duplicate matching and list/form views; resolves invalid `@api.depends` on installation.

### [Added] — Source-derived implementation, not a verified production release
- Workbook-derived QC Parameter Templates: 21 incoming checks and 45 production-stage parameter rules, retaining source textual tolerances and sampling frequency.
- Twenty RM defect codes RM001–RM020, per-log defect picker.
- Product identification field templates (48), materials/film type, intended-use information.
- Versioned TDS specification confirmation, duplicate-to-revise, pending and approved workflow.
- `quality.check` inheritance with parameter/sampling snapshots, measurement log rows, numeric / manual evaluation and native pass validation.
- Batch/lot-aware receipt button; stage-based manufacturing order QC check creation.
- PR → Manager approval → draft RFQ creation, with approved-specification gate only for QC-required products.
- Department consumable reference matrix: 43 items and cadence rules.
- Odoo 19 ACLs, record rules, XML list/form views, master data, installation notes.

### [Docs]
- [2026-10-28] Added workbook-to-module mapping, exact source counts, end-to-end Mermaid workflow, limits, installation instructions and proposed test cases.

### [Compatibility]
- Uses Odoo 19 `models.Constraint`, `list` views and `res.groups.privilege`; no old `attrs` or `tree`.

**Release date of business rules:** Not verified. **Odoo runtime test:** Not executed. This changelog documents implementation in this ZIP only, not historical company releases.
