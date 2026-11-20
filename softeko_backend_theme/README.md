# Softeko Backend Theme — Odoo 19

| Information | Value |
|---|---|
| Technical addon | `softeko_backend_theme` |
| Odoo version | **19.0** (Community backend-focused) |
| Module version | `19.0.1.0.0` |
| Author | **Lamia Akter, Softeko** |
| Category | Customizations |
| License | LGPL-3 |
| Documentation updated | 2026-11-20 |
| Runtime status | **Source reviewed and static checks completed; Odoo 19 server installation NOT tested** |

A fresh Odoo 19 backend extension inspired by the *general visual ideas* of the supplied Odoo 13 MuK theme. This is **not a migration** of MuK code; no MuK addon or external library is required. The original reference ZIP has multiple Odoo 13 packages which must not be installed in Odoo 19.

## Features

- **Company-specific browser favicon**, with optional upload of PNG, JPG, GIF, WebP, or ICO (up to 2 MB). Default fallback is the new Softeko **S** mark.
- **Company/login logo**: edit the native `res.company.logo` from this module's Settings panel. Odoo's standard login template already renders the company logo.
- **Topbar brand logo**: optional separate image; falls back to the native company logo, then the included Softeko wordmark. Enable/disable in Settings.
- **Four color presets** — Midnight Indigo, Ocean Blue, Emerald Green, and Warm Sunset — plus three custom HEX colors (`#RRGGBB`).
- **Desktop app sidebar**: scrollable root app list, current app highlight and quick app switching, Odoo 19 OWL component. On small screens, the standard Odoo mobile navigation remains available.
- **Compact mode** reduces list-cell spacing.
- **Gentle UI refinements**: rounded cards, neutral backgrounds, button/nav styling, login credit.
- **Multi-company fields** on `res.company`: selected company determines appearance; refresh the webclient after switching company or saving settings.

## Installation

1. Put `softeko_backend_theme/` into your Odoo 19 `addons_path` (extract this ZIP first).
2. Restart Odoo and enable Developer Mode.
3. Navigate to **Apps → Update Apps List**, search **Softeko Backend Theme**, and **Install**.
4. Log in as a System Administrator and open **Settings → Softeko Theme**.
5. Choose a palette, logo, favicon and navigation preferences. **Save**, then **hard refresh** the browser (Ctrl+Shift+R).

Only `base_setup` and `web` dependencies are used. No migration scripts, data overwrite or changes to Odoo's original files.

## Configuration

| Settings field | Technical company field | Default | Behavior |
|---|---|---|---|
| Color Preset | `softeko_theme_preset` | Midnight Indigo | One of 4 palettes or Custom |
| Custom Primary | `softeko_primary_color` | `#5465D9` | Validated HEX; used if Custom |
| Custom Navbar | `softeko_navbar_color` | `#192B46` | Validated HEX; used if Custom |
| Custom Background | `softeko_page_color` | `#F4F7FC` | Validated HEX; used if Custom |
| Desktop Sidebar | `softeko_show_sidebar` | True | Displays only on desktop |
| Compact Mode | `softeko_compact_mode` | False | Controls list-cell padding |
| Topbar Logo Toggle | `softeko_show_nav_logo` | True | Topbar logo pseudo-element |
| Topbar Logo | `softeko_nav_logo` | Empty | Company logo → Softeko fallback |
| Login / Company Logo | `logo` | Existing Odoo data | Standard company logo |
| Browser Favicon | `softeko_favicon` | Empty | Softeko favicon fallback |

**Important:** Changing the company logo affects standard Odoo screens using that company logo. The favicon is supplied via a lightweight HTTP route; this module does not change `website` app's own favicon setting.

## Architecture

- `models/res_company.py`: persisted branding configuration and server-side validation. Checks HEX values and favicon signatures/size.
- `models/res_config_settings.py`: editable related settings fields for the selected company.
- `models/ir_http.py`: safely adds the sidebar flag to the webclient `session_info` dictionary.
- `controllers/main.py`: `GET /softeko_theme/favicon` (public), `/softeko_theme/logo` (authenticated), and `/softeko_theme/styles.css` (authenticated). Responses are no-store to refresh when preferences change.
- `views/res_config_settings_views.xml`: administrator-only Odoo 19 `<app>` + `<block>` + `<setting>` screen.
- `views/web_templates.xml`: extends the backend `web.webclient_bootstrap` `x_icon` and appends a dynamic CSS link; extends the login layout with a small credit.
- `static/src/js/sidebar.js` + `static/src/xml/sidebar.xml`: OWL component mounted in the supported `main_components` registry. Uses `menu` service (`getApps`, `getCurrentApp`, `selectMenu`) and the `MENUS:APP-CHANGED` event.
- `static/src/scss/backend.scss`: backend-only presentation; variables provided by the CSS endpoint.
- `security/`: no model ACL additions because there are no new business models; editing is offered in admin-only Settings. Standard `res.company` ACLs still apply at the ORM level; the Settings view restriction is UI-only.

## Behavior and limitations

- A **full page refresh** is needed after configuration changes and often after company switches. No live cross-tab syncing is attempted.
- The sidebar is an additional menu for **desktop** rather than a replacement for Odoo's native Navbar. On mobile Odoo's native sidebar remains untouched.
- Depending on other installed backend themes and Enterprise modules, CSS and menu layouts may need adjustments. Only tested structurally, not on a running Odoo server.
- The favicon route shows the current company's configured image where available. Anonymous sessions use the current public environment company. No website-specific favicon configuration is modified.
- The Odoo login screen's company logo is a standard Odoo feature. This module makes it easy to edit it, but does not force-change existing logos during installation.
- `auth='public'` on favicon route is intentional: favicons must also render before login. Store only public-facing artwork there.

## Proposed QA checklist (not executed)

1. Install on clean Odoo 19 Community with `base_setup` and `web`.
2. In Settings → Softeko Theme, verify all settings save and reload correctly.
3. Switch through each preset, save and refresh; inspect button and navbar color.
4. Set an invalid custom HEX (e.g. `red;`) and verify the server raises validation error.
5. Upload PNG favicon, refresh and verify the browser tab; upload a non-image to confirm rejection.
6. Upload topbar logo and verify fallback behavior when cleared.
7. Upload company login logo and view login in a logged-out browser session.
8. Disable sidebar, refresh and confirm Odoo navigation still works.
9. Check on mobile; standard Odoo menus should continue to work.
10. In multi-company mode, switch company and reload to verify isolated branding.
11. Test dark mode and Enterprise with any other installed third-party themes if applicable.

## Developer quick start

Begin at `__manifest__.py`, then check `views/res_config_settings_views.xml`, `models/res_company.py`, `controllers/main.py`, and `static/src/js/sidebar.js`. Themes are scoped to the backend using `body.o_web_client` and delivered as Odoo 19 assets. When working with new Odoo builds, review selectors/OWL services against the deployed 19.0 version.

## Credits and source reference

**Design/development: Lamia Akter — Softeko.**

The ZIP named `muk_web_theme_mail-13.0.1.0.0.zip` was used as a visual/features reference (left apps sidebar and company-level theme preferences). No MuK source code, fonts, icons or other assets were copied into the new addon.
