/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class RequirementLayerAddButton extends Component {
    static template = "crm_requirement_form.RequirementLayerAddButton";
    static props = { ...standardFieldProps };

    async addLayer() {
        let highestPopulated = 1;
        for (let layerNo = 2; layerNo <= 10; layerNo++) {
            if (this.props.record.data[`layer_${layerNo}_product_tmpl_id`]) {
                highestPopulated = layerNo;
            }
        }
        const currentVisible = Math.max(
            Number(this.props.record.data[this.props.name] || 1),
            highestPopulated
        );
        if (currentVisible < 10) {
            await this.props.record.update({
                [this.props.name]: currentVisible + 1,
            });
        }
    }
}

export class RequirementLayerRemoveButton extends Component {
    static template = "crm_requirement_form.RequirementLayerRemoveButton";
    static props = { ...standardFieldProps, layerNo: { type: Number } };

    async removeLayer() {
        const layerNo = this.props.layerNo;
        const record = this.props.record;
        const currentVisible = Math.max(
            Number(record.data[this.props.name] || 1),
            1
        );
        if (layerNo > currentVisible) {
            return;
        }

        const changes = {};
        if (currentVisible === 1) {
            changes.layer_1_product_tmpl_id = false;
            changes.layer_1_variant_id = false;
        } else {
            for (let target = layerNo; target < currentVisible; target++) {
                const source = target + 1;
                changes[`layer_${target}_product_tmpl_id`] =
                    record.data[`layer_${source}_product_tmpl_id`] || false;
                changes[`layer_${target}_variant_id`] =
                    record.data[`layer_${source}_variant_id`] || false;
            }
            changes[`layer_${currentVisible}_product_tmpl_id`] = false;
            changes[`layer_${currentVisible}_variant_id`] = false;
            changes[this.props.name] = currentVisible - 1;
        }
        await record.update(changes);
    }
}

registry.category("fields").add("crm_req_layer_add_button", {
    component: RequirementLayerAddButton,
    supportedTypes: ["integer"],
});

registry.category("fields").add("crm_req_layer_remove_button", {
    component: RequirementLayerRemoveButton,
    supportedTypes: ["integer"],
    extractProps: ({ options }) => ({
        layerNo: Number(options.layer_no),
    }),
});
