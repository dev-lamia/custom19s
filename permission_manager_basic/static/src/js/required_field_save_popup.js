/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * Only fields explicitly marked by Access Management's Required control
 * receive this dialog. All other form validations remain Odoo-native.
 */
function getMissingControlledRequiredField(controller) {
    const record = controller.model?.root;
    const xmlDoc = controller.archInfo?.xmlDoc;
    if (!record || !xmlDoc) {
        return null;
    }

    for (const node of xmlDoc.querySelectorAll("field[data-pm-required-popup]")) {
        // Nested one2many form/list fields are not fields on this form record.
        if (node.parentElement?.closest("field")) {
            continue;
        }
        const name = node.getAttribute("name");
        if (!name || !(name in record.activeFields) || !record.fields[name]) {
            continue;
        }
        // Honor Odoo's original invisible and conditional required modifiers.
        if (record._isInvisible(name) || !record._isRequired(name)) {
            continue;
        }

        const type = record.fields[name].type;
        const value = record.data[name];
        let empty = false;
        if (["boolean", "float", "integer", "monetary"].includes(type)) {
            // These types are never considered empty by Odoo's form validator.
            continue;
        } else if (type === "one2many" || type === "many2many") {
            empty = !value?.count;
        } else if (type === "json") {
            empty = !value || Object.keys(value).length === 0;
        } else if (type === "html") {
            empty = !value || value.length === 0;
        } else {
            empty = !value;
        }

        if (empty) {
            return node.getAttribute("string") || record.fields[name].string || name;
        }
    }
    return null;
}

patch(FormController.prototype, {
    async save(params) {
        const xmlDoc = this.archInfo?.xmlDoc;
        if (xmlDoc?.querySelector("field[data-pm-required-popup]")) {
            // Flush any focused widget's latest input before checking values.
            await this.model.root.isDirty();
            const label = getMissingControlledRequiredField(this);
            if (label) {
                this.dialogService.add(AlertDialog, {
                    title: _t("Required Field"),
                    body: _t("%s is required. Please fill it in before saving.", label),
                });
                return false;
            }
        }
        return super.save(...arguments);
    },

    async beforeExecuteActionButton(clickParams) {
        // Form footer "Save" buttons call record.save() directly in Odoo 19.
        if (clickParams.special === "save") {
            const xmlDoc = this.archInfo?.xmlDoc;
            if (xmlDoc?.querySelector("field[data-pm-required-popup]")) {
                await this.model.root.isDirty();
                const label = getMissingControlledRequiredField(this);
                if (label) {
                    this.dialogService.add(AlertDialog, {
                        title: _t("Required Field"),
                        body: _t("%s is required. Please fill it in before saving.", label),
                    });
                    return false;
                }
            }
        }
        return super.beforeExecuteActionButton(...arguments);
    },
});
