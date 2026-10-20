/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";
import { SearchModel } from "@web/search/search_model";

const DEFAULT_SEARCH_ACCESS = {
    hideSearchMenu: false,
    hideFilters: false,
    hideGroupBy: false,
    hideFavorites: false,
    hideCustomFilter: false,
    hideCustomGroupBy: false,
    hideSaveCurrentSearch: false,
};

function setupPermissionManagerSearchAccess(component) {
    const orm = useService("orm");
    component.pmSearchAccess = useState({ ...DEFAULT_SEARCH_ACCESS });
    component.env.searchModel.pmHideCustomFilter = false;

    onWillStart(async () => {
        const modelName = component.env.searchModel.resModel;
        if (!modelName) {
            return;
        }
        try {
            const access = await orm.call(
                "permission.manager.search.panel.line",
                "get_search_panel_access",
                [modelName]
            );
            Object.assign(component.pmSearchAccess, {
                hideSearchMenu: Boolean(access?.hide_search_menu),
                hideFilters: Boolean(access?.hide_filters),
                hideGroupBy: Boolean(access?.hide_group_by),
                hideFavorites: Boolean(access?.hide_favorites),
                hideCustomFilter: Boolean(access?.hide_custom_filter),
                hideCustomGroupBy: Boolean(access?.hide_custom_group_by),
                hideSaveCurrentSearch: Boolean(
                    access?.hide_save_current_search
                ),
            });
            // Keep the permission on the shared SearchModel as a final guard.
            // This blocks every caller of spawnCustomFilterDialog(), not only
            // the visible menu/autocomplete entries.
            component.env.searchModel.pmHideCustomFilter =
                component.pmSearchAccess.hideCustomFilter;
        } catch {
            // Keep the standard Odoo search UI available during a temporary
            // module-upgrade/schema mismatch instead of breaking the client.
        }
    });
}

patch(SearchModel.prototype, {
    async spawnCustomFilterDialog() {
        if (this.pmHideCustomFilter) {
            return;
        }
        return super.spawnCustomFilterDialog(...arguments);
    },
});

patch(SearchBarMenu.prototype, {
    setup() {
        super.setup(...arguments);
        setupPermissionManagerSearchAccess(this);
    },

    get otherItems() {
        const items = super.otherItems;
        if (!this.pmSearchAccess?.hideSaveCurrentSearch) {
            return items;
        }
        return items.filter((item) => item.key !== "CustomFavoriteItem");
    },

    async onAddCustomFilterClick() {
        if (this.pmSearchAccess?.hideCustomFilter) {
            return;
        }
        return super.onAddCustomFilterClick(...arguments);
    },
});

patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);
        setupPermissionManagerSearchAccess(this);
    },

    async computeState(options = {}) {
        await super.computeState(options);
        if (!this.pmSearchAccess?.hideCustomFilter) {
            return;
        }

        // Odoo 19 adds a second "Custom Filter..." entry to the autocomplete
        // list whenever text is typed in the search input. Remove that entry
        // too so the Search Panel permission is consistent everywhere.
        for (let index = this.items.length - 1; index >= 0; index--) {
            if (this.items[index].isAddCustomFilterButton) {
                this.items.splice(index, 1);
            }
        }
    },

    onFacetLabelClick(target, facet) {
        // Autocomplete searches create editable domain facets. In standard
        // Odoo, clicking the facet label/pencil opens the same Custom Filter
        // dialog. When Custom Filter is hidden, keep the search facet usable
        // but make it non-editable so there is no alternate entry point.
        if (
            this.pmSearchAccess?.hideCustomFilter &&
            facet?.domain &&
            facet?.type !== "groupBy"
        ) {
            return;
        }
        return super.onFacetLabelClick(...arguments);
    },

    selectItem(item) {
        // Defensive guard in case a stale autocomplete item is still present
        // while assets are reloading/upgrading.
        if (item?.isAddCustomFilterButton && this.pmSearchAccess?.hideCustomFilter) {
            this.inputDropdownState.close();
            this.resetState();
            return;
        }
        return super.selectItem(item);
    },
});
