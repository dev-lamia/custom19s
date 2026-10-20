## [Unreleased] - 2026-10-13

### [Fixed]
- [2026-10-13] Restricted the Dynamic Report application menu to Administrators (`base.group_system`) while preserving the Attendance model Print action for internal users.
- [2026-10-13] Scoped elevated reads to `ir.model` technical metadata needed by runtime report generation; record searches and source-data reads remain under the current user.
- [2026-10-13] Prevented non-admin runtime wizard printing from attempting administrator-only print action synchronization.
- [2026-10-13] Earlier build allowed internal users to see the Dynamic Report root menu by adjusting `views/report_wizard_views.xml`.
- [2026-10-13] Read dynamic field metadata with scoped `sudo()` in the report configuration, runtime wizard, and PDF template to avoid `ir.model.fields` access errors for ordinary internal users.
- [2026-10-13] Avoided administrative report action synchronization when a read-only internal user runs an existing report.

### [Docs]
- [2026-10-13] Documented report sharing scope, source-model access restrictions, and installation verification steps.

---

# Changelog

All entries follow a Keep a Changelog-inspired format. Source review verifies code presence, not runtime behavior.

## [Unreleased] - 2026-10-13

### [Fixed]
- [2026-10-13] Updated `models/report_config.py` to identify float duration fields by actual field name, model field string, and configured report column label, including `Worked Extra Hours` and `Overtime Hours`. These now use signed `HH:MM` formatting instead of decimal hours in the PDF; unrelated float columns are not converted.
- [2026-10-13] Passed the selected report column metadata to `_format_value` for both direct and one-hop relational columns, preserving field-specific context during rendering.

### [Docs]
- [2026-10-13] Added `README.md` with architecture, workflow diagram, report configuration, field display formatting, validation, ACL matrix, installation, QA plan, troubleshooting and developer handover.
- [2026-10-13] Added this `CHANGELOG.md` and separated verified current-code features from the present fix. No manifest version change.

## [19.0.1.0.0] — Current source-code baseline

**Release date: Not verified.** The following features exist in the supplied ZIP; their original implementation dates are not verified.

### [Existing Features — Verified in Source]
- Model-based configuration with ordered direct and relational report columns (`models/report_config.py`).
- Filters, sorting, row limits, company-based document layout, configurable PDF labels/sizes (`models/report_config.py`, `report/`).
- Runtime date/user wizard, period presets and optional user grouping (`models/date_filter_wizard.py`).
- Report preview/print and generated menu/action synchronization (`models/report_config.py`, `data/runtime_action_sync.xml`).
- Role-based configuration ACLs (`security/ir.model.access.csv`).

### [Historical Changes]
- Earlier release history and prior implementation dates: **Not verified**; no release timeline is inferred from ZIP file timestamps or version alone.

## Compatibility

- Odoo 19.0, manifest version `19.0.1.0.0` (not incremented).
- `base` and `web` dependencies; LGPL-3.
- Live server installation, upgrade, and report PDF comparison are **not runtime verified**.
