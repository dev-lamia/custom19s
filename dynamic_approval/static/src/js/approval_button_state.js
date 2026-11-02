/** @odoo-module **/

import { onMounted, onPatched } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.professionalApprovalOrm = useService("orm");
        this.professionalApprovalAction = useService("action");
        this.professionalApprovalRefreshPending = false;
        onMounted(() => this._openProfessionalApprovalSource());
        onMounted(() => this._refreshProfessionalApprovalButtons());
        onPatched(() => this._refreshProfessionalApprovalButtons());
    },


    async _openProfessionalApprovalSource() {
        const root = this.model?.root;
        const modelName = root?.resModel;
        const recordId = root?.resId;
        if (modelName !== "mail.activity" || !recordId) {
            return;
        }
        if (this.professionalApprovalSourceOpening) {
            return;
        }

        this.professionalApprovalSourceOpening = true;
        try {
            const action = await this.professionalApprovalOrm.call(
                "mail.activity",
                "professional_open_source_document",
                [[recordId]]
            );
            if (action) {
                await this.professionalApprovalAction.doAction(action);
            }
        } finally {
            this.professionalApprovalSourceOpening = false;
        }
    },

    async _refreshProfessionalApprovalButtons() {
        if (this.professionalApprovalRefreshPending) {
            return;
        }
        const root = this.model?.root;
        const modelName = root?.resModel;
        const recordId = root?.resId;
        if (!modelName || !recordId) {
            return;
        }

        this.professionalApprovalRefreshPending = true;
        try {
            const states = await this.professionalApprovalOrm.call(
                modelName,
                "professional_button_states",
                [recordId]
            );
            const form = document.querySelector(".o_form_view");
            if (!form) {
                return;
            }
            for (const state of states || []) {
                const selector = `button[name="${CSS.escape(state.method_name)}"]`;
                for (const button of form.querySelectorAll(selector)) {
                    const textNode = [...button.childNodes].find(
                        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                    );
                    const labelSpan = button.querySelector(
                        ".o_button_label, span:not(.fa):not(.oi)"
                    );

                    // Keep the exact native Odoo presentation before changing
                    // the protected button into an approval button. This lets
                    // us restore Send RFQ, Confirm Order, etc. exactly as the
                    // original view defined them after final approval.
                    if (!button.dataset.professionalNativeStored) {
                        const nativeLabel = textNode?.textContent?.trim()
                            || labelSpan?.textContent?.trim()
                            || state.normal_label;
                        button.dataset.professionalNativeStored = "1";
                        button.dataset.professionalNativeLabel = nativeLabel;
                        button.dataset.professionalNativePrimary = button.classList.contains(
                            "btn-primary"
                        ) ? "1" : "0";
                        button.dataset.professionalNativeSecondary = button.classList.contains(
                            "btn-secondary"
                        ) ? "1" : "0";
                    }

                    const label = state.pending_for_user
                        ? _t("Approve")
                        : (button.dataset.professionalNativeLabel || state.normal_label);
                    if (textNode) {
                        textNode.textContent = ` ${label}`;
                    } else if (labelSpan) {
                        labelSpan.textContent = label;
                    } else {
                        button.append(document.createTextNode(` ${label}`));
                    }

                    if (state.pending_for_user) {
                        button.classList.add("btn-primary");
                        button.classList.remove("btn-secondary");
                    } else {
                        button.classList.toggle(
                            "btn-primary",
                            button.dataset.professionalNativePrimary === "1"
                        );
                        button.classList.toggle(
                            "btn-secondary",
                            button.dataset.professionalNativeSecondary === "1"
                        );
                    }
                }
            }
        } finally {
            this.professionalApprovalRefreshPending = false;
        }
    },
});
