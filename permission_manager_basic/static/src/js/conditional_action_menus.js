/** @odoo-module **/

import { ActionMenus } from "@web/search/action_menus/action_menus";
import { patch } from "@web/core/utils/patch";

const STATIC_OPERATION_BY_KEY = {
    export: "export",
    duplicate: "copy",
    archive: "archive",
    unarchive: "unarchive",
    delete: "unlink",
};

patch(ActionMenus.prototype, {
    async _pmGetHiddenBindings(props) {
        const activeIds = props.getActiveIds ? props.getActiveIds() : [];
        return this.orm.call(
            "permission.manager.model.permission.line",
            "get_hidden_bindings_for_records",
            [props.resModel, activeIds]
        );
    },

    async getActionItems(props) {
        const items = await super.getActionItems(...arguments);
        const hidden = await this._pmGetHiddenBindings(props);
        if (hidden.hide_action_menu) {
            return [];
        }

        const hiddenActionIds = new Set(hidden.actions || []);
        const blockedOperations = new Set(hidden.blocked_operations || []);
        const blockSpreadsheet = Boolean(hidden.block_spreadsheet);

        return items.filter((item) => {
            // Spreadsheet also adds selected-record actions such as
            // "Insert in spreadsheet". These do not come from the cogMenu
            // registry, so they must be filtered here as ActionMenus items.
            if (blockSpreadsheet) {
                const spreadsheetMarkers = [
                    item.description,
                    item.key,
                    item.action?.name,
                    item.action?.xml_id,
                    item.action?.tag,
                ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();
                if (spreadsheetMarkers.includes("spreadsheet")) {
                    return false;
                }
            }
            // Odoo 19 static list/form actions preserve these keys in
            // ActionMenus: export, duplicate, archive, unarchive and delete.
            const operation = STATIC_OPERATION_BY_KEY[item.key];
            if (operation && blockedOperations.has(operation)) {
                return false;
            }

            const actionId = item.action?.id ?? item.key;
            return !hiddenActionIds.has(actionId);
        });
    },

    async loadAvailablePrintItems() {
        const items = await super.loadAvailablePrintItems(...arguments);
        const hidden = await this._pmGetHiddenBindings(this.props);
        const hiddenReportIds = new Set(hidden.reports || []);
        return items.filter((item) => {
            const reportId = item.action?.id ?? item.key;
            return !hiddenReportIds.has(reportId);
        });
    },
});
