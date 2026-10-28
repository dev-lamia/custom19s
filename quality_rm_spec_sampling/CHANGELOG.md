# Changelog

## [Unreleased] - 2026-10-28

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
