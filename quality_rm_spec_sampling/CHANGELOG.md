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
