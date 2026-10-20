/** @odoo-module **/

import { onMounted, onPatched } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { x2ManyCommands } from "@web/core/orm_service";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * Build editable values for a new One2many line from an existing line.
 *
 * The duplicate is intentionally created as a NEW/virtual x2many record, the
 * same way "Add a line" works. It is not written to the database until the
 * parent document is saved.
 */

/**
 * Serialize an x2many child record for a CREATE command.
 *
 * This deliberately excludes technical identity/inverse fields while
 * recursively recreating nested one2many rows.  Many2many values are linked
 * to the same records, matching normal Odoo duplication semantics.
 */
function getNestedCreateValues(record) {
    const values = {};
    const inverseField = record.list?.config?.relationField;

    for (const [name, value] of Object.entries(record.data || {})) {
        const field = record.fields?.[name];
        if (!field) {
            continue;
        }
        if (
            name === "id" ||
            name === "display_name" ||
            name === inverseField ||
            field.relatedPropertyField
        ) {
            continue;
        }

        switch (field.type) {
            case "one2many": {
                const children = value?.records || [];
                values[name] = children.map((child) => [
                    x2ManyCommands.CREATE,
                    0,
                    getNestedCreateValues(child),
                ]);
                break;
            }
            case "many2many": {
                const ids = value?.currentIds || [];
                values[name] = ids
                    .filter((id) => typeof id === "number")
                    .map((id) => [x2ManyCommands.LINK, id]);
                break;
            }
            case "many2one":
            case "many2one_reference":
            case "reference":
                values[name] = value ? { ...value } : false;
                break;
            case "properties":
                values[name] = Array.isArray(value)
                    ? value.map((item) => ({ ...item }))
                    : value;
                break;
            case "json":
                values[name] = Array.isArray(value)
                    ? [...value]
                    : value && typeof value === "object"
                      ? { ...value }
                      : value;
                break;
            default:
                values[name] = value;
        }
    }
    return values;
}

function getDuplicateChanges(record, list) {
    const changes = {};
    const inverseField = list.config?.relationField;
    const handleField = list.handleField;

    for (const [name, value] of Object.entries(record.data)) {
        const field = record.fields[name];
        if (!field) {
            continue;
        }

        // The new x2many record gets its own identity, parent relation and
        // sequence/order from addNewRecord().
        if (
            name === "id" ||
            name === "display_name" ||
            name === inverseField ||
            name === handleField ||
            field.relatedPropertyField
        ) {
            continue;
        }

        // Match Odoo's own duplication behaviour: do not force-copy optional
        // readonly/invisible values, but keep required values when needed.
        if (
            record.activeFields?.[name] &&
            (record._isReadonly(name) || record._isInvisible(name)) &&
            !record._isRequired(name)
        ) {
            continue;
        }

        switch (field.type) {
            case "one2many": {
                // Deep-copy child rows as NEW rows as well.  This is what makes
                // a Product Specification duplicate behave like a full-form
                // duplicate instead of copying only the fields visible in the
                // parent list.
                const childRecords = value?.records || [];
                changes[name] = childRecords.map((childRecord) => [
                    x2ManyCommands.CREATE,
                    0,
                    getNestedCreateValues(childRecord),
                ]);
                break;
            }
            case "many2many": {
                // Re-link existing related records on the new line.
                const ids = value?.currentIds || [];
                changes[name] = ids
                    .filter((id) => typeof id === "number")
                    .map((id) => [x2ManyCommands.LINK, id]);
                break;
            }
            case "many2one":
                changes[name] = value ? { ...value } : false;
                break;
            case "many2one_reference":
            case "reference":
                changes[name] = value ? { ...value } : false;
                break;
            case "properties":
                changes[name] = Array.isArray(value)
                    ? value.map((item) => ({ ...item }))
                    : value;
                break;
            case "json":
                changes[name] = Array.isArray(value)
                    ? [...value]
                    : value && typeof value === "object"
                      ? { ...value }
                      : value;
                break;
            default:
                changes[name] = value;
        }
    }

    return changes;
}

/**
 * Universal One2many line duplication for Odoo 19.
 *
 * The patch is on ListRenderer so it also reaches specialised renderers used
 * by standard modules (for example Sales' sol_o2m) and custom modules.
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => this._psSyncDuplicateButtons());
        onPatched(() => this._psSyncDuplicateButtons());
    },

    get hasActionsColumn() {
        return super.hasActionsColumn || this._psCanDuplicateOne2manyLines;
    },

    get _psCanDuplicateOne2manyLines() {
        const list = this.props.list;
        return Boolean(
            this.isX2Many &&
                list?.config?.relationField &&
                this.canCreate &&
                !this.props.readonly &&
                !list.model?.useSampleModel
        );
    },

    _psSyncDuplicateButtons() {
        const root = this.rootRef?.el;
        if (!root) {
            return;
        }

        if (!this._psCanDuplicateOne2manyLines) {
            root.querySelectorAll(".o_ps_duplicate_line").forEach((button) => {
                button.remove();
            });
            return;
        }

        const rows = root.querySelectorAll("tbody tr.o_data_row[data-id]");
        for (const row of rows) {
            if (row.querySelector(".o_ps_duplicate_line")) {
                continue;
            }

            const record = this._psFindRecordByRowId(row.dataset.id);
            if (!record) {
                continue;
            }

            // Keep section/combo-specific row semantics untouched.
            if (row.querySelector(":scope > td.o_list_section_options")) {
                continue;
            }

            let actionCell = row.querySelector(":scope > td.o_list_record_remove");
            if (!actionCell) {
                actionCell = document.createElement("td");
                actionCell.className =
                    "o_list_record_remove w-print-0 p-print-0 text-center o_ps_action_cell";
                actionCell.tabIndex = -1;
                row.appendChild(actionCell);
            }

            const button = document.createElement("button");
            button.type = "button";
            button.className = "fa fa-copy d-print-none o_ps_duplicate_line";
            button.name = "duplicate_line";
            button.title = _t("Duplicate Line");
            button.setAttribute("aria-label", _t("Duplicate Line"));
            button.tabIndex = -1;

            button.addEventListener("click", async (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                await this._psDuplicateRecord(record, button);
            });

            const deleteButton = actionCell.querySelector(
                "button[name='delete'], button.fa-trash-o, button.fa-times"
            );
            if (deleteButton) {
                actionCell.insertBefore(button, deleteButton);
            } else {
                actionCell.appendChild(button);
            }
        }
    },

    _psFindRecordByRowId(rowId, list = this.props.list) {
        if (!rowId || !list) {
            return null;
        }

        const record = list.records?.find(
            (candidate) => String(candidate.id) === String(rowId)
        );
        if (record) {
            return record;
        }

        for (const group of list.groups || []) {
            const groupedRecord = this._psFindRecordByRowId(rowId, group.list);
            if (groupedRecord) {
                return groupedRecord;
            }
        }
        return null;
    },

    async _psDuplicateRecord(record, button) {
        if (button.dataset.clicked) {
            return;
        }
        button.dataset.clicked = "1";
        button.disabled = true;

        try {
            const list = this.props.list;
            if (!list?.config?.relationField || typeof list.addNewRecord !== "function") {
                this.notificationService.add(
                    _t("This line cannot be duplicated from this view."),
                    { type: "warning" }
                );
                return;
            }

            // Flush the currently edited widget value first, exactly as the
            // normal x2many "Add a line" flow does.
            if (list.editedRecord) {
                const proms = [];
                list.model.bus.trigger("NEED_LOCAL_CHANGES", { proms });
                const updatePromise = list.editedRecord._updatePromise;
                if (updatePromise) {
                    proms.push(updatePromise);
                }
                await Promise.all(proms);

                const leftEditMode = await list.leaveEditMode({ canAbandon: false });
                if (!leftEditMode) {
                    return;
                }
            }

            const changes = getDuplicateChanges(record, list);

            // IMPORTANT: create a virtual/new line just like "Add a line".
            // No parent save and no ORM copy() happen here.
            const newRecord = await list.addNewRecord({
                position: "bottom",
                context: list.context || {},
                mode: "edit",
            });

            if (Object.keys(changes).length) {
                await newRecord.update(changes);
            }

            // Keep the duplicated row open for immediate editing.
            if (!newRecord.isInEdition) {
                await newRecord.switchMode("edit");
            }
        } catch (error) {
            this.notificationService.add(
                error?.data?.message ||
                    error?.message ||
                    _t("Could not duplicate this line."),
                { type: "danger" }
            );
        } finally {
            delete button.dataset.clicked;
            button.disabled = false;
        }
    },
});
