# Changelog

## [19.0.1.0.12] — 2026-11-09

### [Changed]
- Replaced the operational QCS/TDS approval and activation workflow with direct **Product → QC Master → Receipt / Production Quality Check**.
- Removed TDS/QCS menu, activate and approval screens, and QC Standards product smart button from the user-facing interface.
- Purchase Orders no longer require an active QCS; normal Odoo Purchase validation stays intact.
- Added master-driven per-receipt and per-production-stage Quality Check generation and automatic sample-row preparation.
- Simplified Product, Inspection, Measurement and Master menus and forms.
- Resolved simple numeric and `Nominal ± percentage` Film Thickness limits when the corresponding product property is present.
- Production QC now uses a process-stage selection wizard rather than an active Production QCS.

### [Compatibility]
- Retained legacy QCS/PR models, XML IDs, view definitions and stored historical measurements to prevent destructive Odoo view-inheritance or foreign-key errors during upgrade.
- Existing QCS values are not silently overwritten, deleted or imported into the global master rules. Source-specific limits must be reviewed before using this version.
- No new AQL acceptance, stock blocking or auto-release workflow was inferred from the workbook.

### [Tests]
- Added proposed staging tests for direct master-driven rule selection and product-nominal formula resolution. Static validation only; no live Odoo installation was run.
