# Changelog — Artwork Project Flow

Changes are recorded in a Keep a Changelog-inspired format. **Documentation dates are not assumed to be earlier feature release dates.**

## [Unreleased] — 2026-11-05

### [Changed]

- **[2026-11-05] Repeat Job artwork creation enabled.** Removed the Repeat Job exclusion from `sale.order.action_create_artwork()` and `artwork.project.create.wizard.action_create_project()`.
- **[2026-11-05] Create Artwork button visibility corrected.** The eligibility computation now uses only artwork **owned by the current Sale Order** to prevent duplicates. An earlier artwork linked through the Repeat Job smart button no longer hides the button. The existing confirmed-SO and posted-customer-invoice UI conditions remain in effect. See `models/sale_order.py` and `views/sale_order_views.xml`.
- **[2026-11-05] Retained per-SO duplicate protection.** After a repeat order creates its own Project/Task records, the Create Artwork button becomes hidden; the wizard continues to reject creating artwork twice for that same SO. See `wizard/artwork_project_wizard.py`.

### [Documentation]

- **[2026-11-05]** Added `README.md` detailing current business behavior, workflows, data ownership, validations, dependencies, security, technical references, setup, troubleshooting and proposed QA tests.
- **[2026-11-05]** Added `CHANGELOG.md` with source-verified current feature inventory and the changes in this update.

### [Compatibility]

- **[2026-11-05]** No manifest-version change (`19.0.0.1`); no changes to the related CRM Requirement Form module, Job Code generation, GDN generation, or the previous-artwork lookup logic.

## [19.0.0.1] — Date: Not verified

### Verified source-code baseline (not a claimed historical release)

The supplied ZIP includes the following already-implemented features. Their original implementation dates and prior change history were **not verified**:

- Creates an Artwork Project and Task for each eligible Sales Order line with a Job Code, optionally using a Project template.
- Links created Tasks to the originating Sale Order and Sale Order Line and stores Job Code as the task/project name.
- Provides the Artwork smart button and source-design/Job Code lookup for earlier Repeat Job artwork.
- Displays the latest matching confirmed Repeat Job Sales Order on task forms and kanban cards, without reassigning original task ownership.
- Displays Job Code and GDN links on the Artwork task tab and Sales Order references in Project views.
- Prevents duplicate artwork creation for an individual Sale Order.
- Depends on `sale_management`, `project`, and `crm_requirement_form`.

**Runtime status:** Static source and XML validation only. A live Odoo module upgrade and business-flow tests have not been executed for this archive.
