# Changelog — Access Management (`permission_manager_basic`)

This changelog follows a *Keep a Changelog*-inspired structure and distinguishes a verified **source-code baseline** from verified **dated changes**. The manifest version is **19.0.1.0.14** and is not incremented by this documentation update.

## [Unreleased] — 2026-11-23

### [Store UI Previews / Animation Preservation] — 2026-11-23
- **[2026-11-23]** Added a visual overview image and eight individually matched illustrative setup UI preview images beside the corresponding policy-tab explanations in `static/description/index.html`.
- **[2026-11-23]** Kept the existing detailed configuration guidance, real Odoo product screenshots, sky-blue Softeko branding, developer links and support details. The previews are labeled illustrative to distinguish them from the real Odoo screenshots elsewhere on the page.
- **[2026-11-23]** Retained and verified the animated promotional banner at `static/description/images/security_animated.gif` without adding JavaScript or custom animation runtime.
- **[2026-11-23]** Updated `README.md`; no changes were made to executable Python, JS, CSS, XML, security data or manifest and the module version is unchanged.

### [Store Description / Tab Guide] — 2026-11-23
- **[2026-11-23]** Added a sky-blue policy-tab reference to `static/description/index.html`, documenting each of the eight main policy tabs, three Field Controls sub-tabs, configuration choices, use-case examples and differences between navigation, model, record and field rules.
- **[2026-11-23]** Added anchor-based quick navigation and plain HTML explanation cards; no JavaScript, custom animation libraries or executable module files were changed.
- **[2026-11-23]** Preserved the existing Softeko animation, illustrations, screenshots, developer attribution, website and support links. The guidance explicitly notes pre-existing source-verification limitations; it is not a runtime certification.
- **[2026-11-23]** Updated `README.md` with a summary of the new Apps Store policy-tab guide.

### [Contacts / Support] — 2026-11-23
- **[2026-11-23]** Linked developer **Lamia** to the profile URL already documented in the original manifest, `https://lamia-akter.odoo.com/`, in the sky-blue store description. The profile URL's live availability was not independently verified.
- **[2026-11-23]** Included the official Softeko website `https://www.softeko.co/` and support/contact page `https://www.softeko.co/contact/` in the developer/support cards. External website links may be invalidated by the Odoo Apps Store HTML sanitizer.
- **[2026-11-23]** Added `support: contact@softeko.co` to `__manifest__.py` (Odoo Apps support metadata) and an allowed `mailto:` contact link in the store description. The previously configured `website` field, app version, animation, and functionality remain unchanged.
- **[2026-11-23]** Updated `README.md` with the contact URLs, their source, and Odoo Apps link-sanitization limitations.

### [Style / Storefront] — 2026-11-23
- **[2026-11-23]** Redesigned `static/description/index.html` in a consistent sky-blue Softeko visual identity with a responsive feature showcase and original Odoo module screenshots.
- **[2026-11-23]** Replaced the store icon and created `images/main_screenshot.png` and `images/feature_model_permissions.png`, using actual supplied policy/model screenshots in the visual compositions.
- **[2026-11-23]** Added the self-contained `images/security_animated.gif` promotional animation. No JavaScript or CSS animation is used in the store description.
- **[2026-11-23]** Added the manifest `images` metadata for the cover and original screenshots and fixed a typo in the manifest summary. The manifest module version remains `19.0.1.0.14`.
- **[2026-11-23]** Removed off-platform navigation links from the store description to align with Odoo Apps vendor guidelines; Softeko attribution remains present.

### [Docs] — 2026-11-23
- **[2026-11-23]** Documented store presentation assets and compatibility expectations in the README. No executable business logic, security rules, views, or backend assets were modified.

## [Unreleased] — 2026-11-09

### [Changed / Security] — 2026-11-09, source-verified against the preceding uploaded ZIP
- **[2026-11-09]** Consolidated **Access Management User** and **Access Management Administrator** into one active, user-selectable **Access Management** checkbox (`permission_manager_basic.group_permission_manager_user`). This replaces the previous read-only user / full CRUD administrator split.
- **[2026-11-09]** Gave this single group Read, Write, Create and Delete permissions on all ten custom `permission.manager.*` models (1/1/1/1) in `security/ir.model.access.csv`; removed the old administrator-specific ACL rows.
- **[2026-11-09]** Removed Settings Administrator (`base.group_system`) as an automatic app grant by deleting previous implied-group relationships, retiring `group_permission_manager_admin` and its old ACLs in `security/security.xml`.
- **[2026-11-09]** Replaced old Settings Administrator restrictions on the Access Management root and Policies menus with the single group's restriction, explicitly removing the prior group grant in `views/menu_views.xml` for upgrades.
- **[2026-11-09]** Changed Activate/Deactivate Policy button visibility to the single group in `views/permission_manager_views.xml`. No other business logic was changed by this previously delivered access-control update.

### [Docs] — 2026-11-09, this ZIP only
- **[2026-11-09]** Updated `README.md` to explain the single checkbox, group-independent app eligibility, effective ACL matrix, upgrade assignment steps, migration caveats, troubleshooting, and additional proposed security tests.
- **[2026-11-09]** Updated `CHANGELOG.md` to record the earlier security/code changes verifiable by ZIP comparison and separate them from the present **documentation-only** package revision. All other archive entries, including existing security/XML/CSV changes, are preserved byte-for-byte.

### Earlier recorded work — 2026-11-02


### [Fixed] — verified against the preceding ZIP in this conversation
- **[2026-11-02]** Added a form-save popup for policy-controlled Required fields by creating `static/src/js/required_field_save_popup.js`, registering it in the existing manifest backend assets, and tagging applicable form fields in `Base.get_view()` with `data-pm-required-popup`.
- **[2026-11-02]** Updated existing server-side Required validation messages in `Base._permission_manager_check_field_values()` so a single missing field is reported by label with `is required. Please fill it in before saving.`, with a combined message for multiple missing fields. These code differences are observable between the original user ZIP and the corrected ZIP from the previous response; this documentation update makes **no further code changes**.

### [Docs]
- **[2026-11-02]** Added `README.md` at the module root, documenting module metadata, purpose, technical architecture, workflows, feature inventory, policies, configuration fields, validations, data relationships, security/access-control matrix, installation, troubleshooting, limitations, and proposed tests.
- **[2026-11-02]** Added `CHANGELOG.md` at the module root, separating the source-verified current functionality from dated historical change records and noting unverified release dates.
- **[2026-11-02]** Documented the already-present Field Controls → Required form-save popup, including the `Base.get_view()` marker, `FormController` handlers, backend required validation, supported cases and limitations.
- **[2026-11-02]** Added explicit implementation caveats for stored relational `selection_domain` configuration and Record Domain Write/Create/Delete scope checkboxes where runtime enforcement could not be established from the source.

### [Compatibility]
- **[2026-11-02]** Documentation-only package update. No Python, JS, CSS, XML, CSV, images, manifest, security records or business logic changed; manifest version remains `19.0.1.0.14`.

## [19.0.1.0.14] — release date: Not verified

### Verified current module features (baseline, **not a newly dated release**)

The following capabilities exist in the supplied ZIP and are documented as a **current code inventory**. The source does **not** establish when each feature was originally released.

- **[Existing; date not verified]** Policy assignment to direct users, optionally to group members, with company scope and activation/deactivation (`PermissionManagerPolicy`).
- **[Existing; date not verified]** Navigation menu/submenu hiding through `PermissionManagerHiddenMenuLine` and `IrUiMenu._visible_menu_ids()`.
- **[Existing; date not verified]** Model operation restrictions, Hide Model, report/action restriction, and view type controls through `PermissionManagerModelPermissionLine`, `Base`, and backend JS patches.
- **[Existing; date not verified]** Search Panel controls for Filters, Group By, Favorites, Custom Filter, Custom Group By and Save Current Search (`PermissionManagerSearchPanelLine`, `search_menu_access.js`).
- **[Existing; date not verified]** Unified Field Controls supporting Hide, Read Only, Required, Import/Export flags, conditional attributes and stored domain configuration (`PermissionManagerFieldPermissionLine`).
- **[Existing; date not verified]** **Required Field popup on form Save**, with the field-name message **`<Field Label> is required. Please fill it in before saving.`** (`Base.get_view()`, `static/src/js/required_field_save_popup.js`). The supplied code contains the implementation, but its original implementation date is not independently verified.
- **[Existing; date not verified]** Legacy conditional field-state rules (`PermissionManagerFieldStateRuleLine`).
- **[Existing; date not verified]** Read-scope record visibility filtering in web search/list views (`PermissionManagerRecordDomainRuleLine`, `Base.web_search_read()`).
- **[Existing; date not verified]** Discovery and UI hiding of selected buttons/notebook tabs (`PermissionManagerHideItem`, `PermissionManagerHideButtonTabLine`, `Base.get_view()`).
- **[Existing; date not verified]** Chatter visibility options (`PermissionManagerChatterVisibilityLine`, chatter CSS).
- **[Existing; date not verified]** Force Read-Only, Block Login, Block Debug Mode, and Hide Export Available Fields global policy flags (`PermissionManagerPolicy`, `ResUsers`, backend JS/XML).
- **[Current behavior; changed 2026-11-09]** Single **Access Management** app group and explicit checkbox, ten full CRUD ACL rows, no Settings Administrator implication, and root/Policies/button groups tied to the single group (`security/*`, `views/menu_views.xml`, `views/permission_manager_views.xml`).
- **[Existing; date not verified]** Cache invalidation on many policy/rule changes and selected user attribute changes; module UI assets and stale-asset cleanup.

### Historical changes

- **Date: Not verified** for older releases. No dated release record, git commit history, or release notes are bundled in this ZIP. The 2026-11-02 Required-popup correction is recorded in existing documentation from prior ZIP comparison; the **2026-11-09 single-checkbox access control** is independently confirmed by diffing the two supplied November 9 ZIPs. The manifest version’s original release date and dates of other existing features remain unverified.

### Source / verification scope

- Verified from `__manifest__.py`, `models/permission_manager.py`, `views/*`, `security/*`, and `static/src/*` in the input ZIP.
- Source-code review is **not** evidence of successful Odoo server or browser runtime testing.
- `README.md` contains the detailed configuration and implementation review, the security matrix, proposed QA cases and known limitations.

---

**Documentation Updated:** 2026-11-09  
**Current Manifest Version:** `19.0.1.0.14`  
**Latest Verified Release Date:** Not verified  
**Change Scope of this ZIP vs. the previous single-checkbox ZIP:** `README.md` and `CHANGELOG.md` only. (The earlier 2026-11-09 access-control ZIP already modified security and views.)
