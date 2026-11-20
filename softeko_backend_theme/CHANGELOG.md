# Changelog — Softeko Backend Theme

Format inspired by Keep a Changelog. Dates below are documentation/build dates, not claimed historical MuK release dates.

## [Unreleased] - 2026-11-20

### [Docs]
- [2026-11-20] Documented configuration fields, architecture, endpoints, installation and proposed QA checklist.
- [2026-11-20] Recorded source-reference limitations and absence of runtime testing.

## [19.0.1.0.0] - 2026-11-20

### [Added]
- [2026-11-20] Created new Odoo 19-compatible Softeko addon (not a migrated MuK source tree).
- [2026-11-20] Added company-level theme presets, validated custom colors, optional compact mode and topbar branding.
- [2026-11-20] Added modern OWL desktop app sidebar using Odoo 19 menu service.
- [2026-11-20] Added company favicon upload, validation, browser favicon route and Softeko default assets.
- [2026-11-20] Added company/login logo editing through native Odoo company logo field.
- [2026-11-20] Added administrator-only Softeko Theme Settings app, login credit and source documents.

### [Security]
- [2026-11-20] Added strict HEX validation and favicon file-size/signature checks, without broad model access rules.
- [2026-11-20] Restricted CSS and logo HTTP routes to authenticated users; favicon route serves only public-facing artwork.

### [Migration / Compatibility]
- [2026-11-20] Built for Odoo 19 webclient assets/OWL architecture; no deprecated Odoo 13 MuK APIs/dependencies reused.

**Verification:** static file/XML/Python checks only. Deployment on a running Odoo 19 instance is not verified.
