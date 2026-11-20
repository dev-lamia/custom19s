/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { CogMenu } from "@web/search/cog_menu/cog_menu";

const cogMenuRegistry = registry.category("cogMenu");
const SPREADSHEET_LABELS = [
    _t("Spreadsheet"),
    _t("Insert in spreadsheet"),
    _t("Insert list in spreadsheet"),
];

function normalize(value) {
    return String(value || "").trim().toLowerCase();
}

function isSpreadsheetText(value) {
    const text = normalize(value);
    if (!text) {
        return false;
    }
    if (text.includes("spreadsheet")) {
        return true;
    }
    return SPREADSHEET_LABELS.some((label) => text.includes(normalize(label)));
}

function componentMarkers(component) {
    if (!component) {
        return "";
    }

    const componentNames = Object.keys(component.components || {});
    const markers = [
        component.name,
        component.template,
        component.prototype?.constructor?.name,
        ...componentNames,
    ];

    try {
        markers.push(Function.prototype.toString.call(component));
    } catch {
        // Ignore non-standard component values.
    }

    return normalize(markers.filter(Boolean).join(" "));
}

function isSpreadsheetRegistryItem(item) {
    const markers = [
        item?.pmRegistryKey,
        item?.key,
        item?.description,
        item?.name,
        componentMarkers(item?.Component),
    ]
        .filter(Boolean)
        .join(" ");
    return isSpreadsheetText(markers);
}

function hideElement(element) {
    if (!element) {
        return;
    }
    element.classList.add("d-none");
    element.setAttribute("data-pm-spreadsheet-hidden", "1");
}

function hideRenderedSpreadsheetEntry() {
    // Odoo 19 has two spreadsheet entry points in list views:
    // 1) Cog menu: Spreadsheet -> Insert list in spreadsheet
    // 2) Selected-record Actions: Insert in spreadsheet
    // Enterprise modules can render either entry after the base CogMenu has
    // already mounted, so this DOM guard complements the registry/action
    // filtering and also covers translated/nested menu rendering.
    const roots = document.querySelectorAll(
        ".o_cp_action_menus, .o_control_panel, .dropdown-menu"
    );
    for (const root of roots) {
        const candidates = root.querySelectorAll(
            ".dropdown-item, [role='menuitem'], button, a"
        );
        for (const candidate of candidates) {
            if (!isSpreadsheetText(candidate.textContent)) {
                continue;
            }

            // Prefer hiding exactly the menu row. For a nested Spreadsheet
            // trigger, hide its own dropdown wrapper rather than the complete
            // cog menu root.
            const row = candidate.closest(".dropdown-item");
            if (row) {
                hideElement(row);
                continue;
            }

            const nestedDropdown = candidate.closest(".o-dropdown");
            if (
                nestedDropdown &&
                !nestedDropdown.classList.contains("o_cp_action_menus")
            ) {
                hideElement(nestedDropdown);
                continue;
            }

            hideElement(candidate);
        }
    }
}

patch(CogMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.pmBlockSpreadsheet = false;
        this.pmSpreadsheetObserver = null;

        onMounted(() => {
            this._pmEnsureSpreadsheetDomGuard();
            this._pmScheduleSpreadsheetDomCleanup();
        });

        onWillUnmount(() => {
            this.pmSpreadsheetObserver?.disconnect();
            this.pmSpreadsheetObserver = null;
        });
    },

    _pmCurrentModelName() {
        return this.props.resModel || this.env.searchModel?.resModel || false;
    },

    async _pmSpreadsheetIsBlocked() {
        const modelName = this._pmCurrentModelName();
        if (!modelName) {
            return false;
        }
        try {
            return Boolean(
                await this.orm.call(
                    "permission.manager.model.permission.line",
                    "is_spreadsheet_blocked_for_current_user",
                    [modelName]
                )
            );
        } catch {
            // Never break the standard Odoo cog menu during a temporary
            // module-upgrade/schema mismatch.
            return false;
        }
    },

    _pmEnsureSpreadsheetDomGuard() {
        if (!this.pmBlockSpreadsheet || this.pmSpreadsheetObserver) {
            return;
        }
        this.pmSpreadsheetObserver = new MutationObserver(() => {
            hideRenderedSpreadsheetEntry();
        });
        this.pmSpreadsheetObserver.observe(document.body, {
            childList: true,
            subtree: true,
        });
    },

    _pmScheduleSpreadsheetDomCleanup() {
        if (!this.pmBlockSpreadsheet) {
            return;
        }
        this._pmEnsureSpreadsheetDomGuard();
        requestAnimationFrame(() => hideRenderedSpreadsheetEntry());
        setTimeout(() => hideRenderedSpreadsheetEntry(), 0);
    },

    async _registryItems() {
        const items = await super._registryItems(...arguments);
        this.pmBlockSpreadsheet = await this._pmSpreadsheetIsBlocked();
        if (!this.pmBlockSpreadsheet) {
            return items;
        }

        // Odoo core's _registryItems() keeps Component/group/key but drops the
        // original registry key. Spreadsheet integrations frequently have the
        // most reliable identifier there, so restore it by matching the
        // component reference from getEntries().
        const registryKeyByComponent = new Map(
            cogMenuRegistry
                .getEntries()
                .map(([registryKey, value]) => [value?.Component, registryKey])
        );
        const enrichedItems = items.map((item) => ({
            ...item,
            pmRegistryKey: registryKeyByComponent.get(item.Component),
        }));

        this._pmScheduleSpreadsheetDomCleanup();
        return enrichedItems.filter((item) => !isSpreadsheetRegistryItem(item));
    },

    async loadPrintItems() {
        const result = await super.loadPrintItems(...arguments);
        this._pmScheduleSpreadsheetDomCleanup();
        return result;
    },
});
