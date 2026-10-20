/** @odoo-module **/

import { ExportDataDialog } from "@web/views/view_dialogs/export_data_dialog";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";

patch(ExportDataDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.pmHideExportAvailableFields = false;

        onWillStart(async () => {
            try {
                this.pmHideExportAvailableFields = await this.orm.call(
                    "permission.manager.policy",
                    "is_current_user_export_available_fields_hidden",
                    []
                );
            } catch (error) {
                this.pmHideExportAvailableFields = false;
            }
        });
    },
});
