/** @odoo-module **/

import {
    onMounted,
    onWillStart,
    onWillUnmount,
} from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

const HIDDEN_MARKER = "data-pm-spreadsheet-hidden";

function normalize(value) {
    return String(value || "").trim().toLowerCase();
}

function elementMarkers(element) {
    return normalize(
        [
            element?.textContent,
            element?.getAttribute?.("title"),
            element?.getAttribute?.("aria-label"),
            element?.getAttribute?.("data-tooltip"),
            element?.getAttribute?.("name"),
        ]
            .filter(Boolean)
            .join(" ")
    );
}

function isSpreadsheetEntry(element) {
    return elementMarkers(element).includes("spreadsheet");
}

function hideTarget(element) {
    if (!element || element.getAttribute(HIDDEN_MARKER) === "1") {
        return;
    }
    element.classList.add("d-none");
    element.setAttribute(HIDDEN_MARKER, "1");
}

function hideSpreadsheetEntry(element) {
    if (!element || !isSpreadsheetEntry(element)) {
        return;
    }

    const dropdownItem = element.closest(".dropdown-item, [role='menuitem']");
    if (dropdownItem) {
        hideTarget(dropdownItem);
        return;
    }

    // The Spreadsheet parent in the cog menu is a nested dropdown. Hide the
    // whole nested wrapper, but never hide the main Actions/Cog menu itself.
    const nestedDropdown = element.closest(".o-dropdown");
    if (
        nestedDropdown &&
        !nestedDropdown.classList.contains("o_cp_action_menus") &&
        !nestedDropdown.closest(".o_cp_action_menus")?.isSameNode?.(nestedDropdown)
    ) {
        hideTarget(nestedDropdown);
        return;
    }

    hideTarget(element);
}

function hideSpreadsheetEntries() {
    // Cover every Odoo 19 model-view entry point:
    // - List cog menu: Spreadsheet -> Insert list in spreadsheet
    // - Selected-record Actions: Insert in spreadsheet
    // - Pivot view: Insert in Spreadsheet
    // - Graph view: Insert in Spreadsheet
    // - Any equivalent button/menu rendered by Enterprise spreadsheet addons
    // Dropdowns can be portalled outside the control panel, therefore both the
    // active action and visible dropdown menus are scanned.
    const selectors = [
        ".o_action_manager .o_control_panel button",
        ".o_action_manager .o_control_panel a",
        ".o_action_manager .o_control_panel [role='menuitem']",
        ".o_action_manager .o_control_panel [role='button']",
        ".o_action_manager .o_view_controller button",
        ".o_action_manager .o_view_controller a",
        ".dropdown-menu.show .dropdown-item",
        ".dropdown-menu.show [role='menuitem']",
        ".dropdown-menu.show button",
        ".dropdown-menu.show a",
    ];

    for (const element of document.querySelectorAll(selectors.join(","))) {
        hideSpreadsheetEntry(element);
    }
}

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.pmSpreadsheetBlockedForModel = false;
        this.pmSpreadsheetObserver = null;

        onWillStart(async () => {
            this.pmSpreadsheetBlockedForModel =
                await this._pmIsSpreadsheetBlockedForCurrentModel();
        });

        onMounted(() => {
            if (!this.pmSpreadsheetBlockedForModel) {
                return;
            }
            this._pmStartSpreadsheetObserver();
            this._pmHideSpreadsheetEntries();
        });

        onWillUnmount(() => {
            this.pmSpreadsheetObserver?.disconnect();
            this.pmSpreadsheetObserver = null;
        });
    },

    _pmSpreadsheetModelName() {
        return (
            this.env.searchModel?.resModel ||
            this.env.config?.resModel ||
            this.env.searchModel?.globalContext?.active_model ||
            false
        );
    },

    async _pmIsSpreadsheetBlockedForCurrentModel() {
        const modelName = this._pmSpreadsheetModelName();
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
            // A permission module must never make the standard control panel
            // unusable while the module is being upgraded.
            return false;
        }
    },

    _pmHideSpreadsheetEntries() {
        if (!this.pmSpreadsheetBlockedForModel) {
            return;
        }
        requestAnimationFrame(() => hideSpreadsheetEntries());
        setTimeout(() => hideSpreadsheetEntries(), 0);
        setTimeout(() => hideSpreadsheetEntries(), 100);
    },

    _pmStartSpreadsheetObserver() {
        if (this.pmSpreadsheetObserver || !this.pmSpreadsheetBlockedForModel) {
            return;
        }
        this.pmSpreadsheetObserver = new MutationObserver(() => {
            hideSpreadsheetEntries();
        });
        this.pmSpreadsheetObserver.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["class", "aria-expanded"],
        });
    },
});
