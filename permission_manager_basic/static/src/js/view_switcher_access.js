/** @odoo-module **/

import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

function normalizeViewType(viewType) {
    return viewType === "tree" ? "list" : viewType;
}

/**
 * Hide model-restricted view types from Odoo 19's ControlPanel switcher.
 *
 * Important: do not remove view architectures from get_views()/get_view().
 * Doing that can make OWL try to load an undefined view description. Instead,
 * filter the already-built `env.config.viewSwitcherEntries` array before the
 * first ControlPanel render. The stock Odoo template then naturally renders
 * only the allowed switcher buttons on desktop and mobile.
 */
patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.pmHiddenViewTypes = new Set();

        onWillStart(async () => {
            const modelName = this.env.searchModel?.resModel;
            if (!modelName) {
                return;
            }

            let hiddenTypes = [];
            try {
                hiddenTypes = await this.orm.call(
                    "permission.manager.model.permission.line",
                    "get_hidden_view_types_for_current_user",
                    [modelName]
                );
            } catch {
                // Never let a temporary asset/schema mismatch break Odoo UI.
                return;
            }

            this.pmHiddenViewTypes = new Set(
                (hiddenTypes || []).map(normalizeViewType)
            );
            if (!this.pmHiddenViewTypes.size) {
                return;
            }

            const entries = this.env.config.viewSwitcherEntries;
            if (!Array.isArray(entries)) {
                return;
            }

            const visibleEntries = entries.filter(
                (entry) =>
                    !this.pmHiddenViewTypes.has(normalizeViewType(entry.type))
            );

            // Mutate in place so Odoo's original ControlPanel template,
            // hotkey cycling and any other consumer of the same array all see
            // the restricted list. This also works if our XML inheritance is
            // not part of a previously cached asset bundle.
            entries.splice(0, entries.length, ...visibleEntries);
        });
    },

    get pmViewSwitcherEntries() {
        const entries = this.env.config.viewSwitcherEntries || [];
        if (!this.pmHiddenViewTypes?.size) {
            return entries;
        }
        return entries.filter(
            (entry) =>
                !this.pmHiddenViewTypes.has(normalizeViewType(entry.type))
        );
    },

    switchView(viewType, newWindow) {
        if (this.pmHiddenViewTypes?.has(normalizeViewType(viewType))) {
            return;
        }
        return super.switchView(...arguments);
    },

    cycleThroughViews() {
        const entries = this.env.config.viewSwitcherEntries || [];
        if (!entries.length) {
            return;
        }

        const currentViewType = normalizeViewType(this.env.config.viewType);
        const currentIndex = entries.findIndex(
            (entry) => normalizeViewType(entry.type) === currentViewType
        );
        const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % entries.length : 0;
        this.switchView(entries[nextIndex].type);
    },
});
