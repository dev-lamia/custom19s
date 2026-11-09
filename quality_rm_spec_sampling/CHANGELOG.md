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
