/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";

/**
 * Preserve the Select GDN dropdown on quotations, and show the linked GDN
 * record as a clickable value after the Sale Order is confirmed.
 */
export class GdnLinkMany2OneField extends Component {
    static components = { Many2OneField };
    static props = Many2OneField.props;
    static template = xml`
        <t t-if="showGdnLink">
            <a t-att-href="gdnUrl" class="fw-semibold o_form_uri">
                <t t-esc="gdnLabel"/>
            </a>
        </t>
        <t t-else="">
            <Many2OneField t-props="props"/>
        </t>
    `;

    get selectedGdn() {
        return this.props.record.data[this.props.name];
    }

    get gdnId() {
        const value = this.selectedGdn;
        return Array.isArray(value) ? value[0] : value?.id;
    }

    get showGdnLink() {
        return Boolean(this.gdnId) && ["sale", "done", "cancel"].includes(
            this.props.record.data.gdn_order_state
        );
    }

    get gdnLabel() {
        const value = this.selectedGdn;
        return (
            this.props.record.data.gdn_number ||
            (Array.isArray(value) ? value[1] : value?.display_name) ||
            "GDN"
        );
    }

    get gdnUrl() {
        return `/web#id=${this.gdnId}&model=sale.gdn.configuration&view_type=form`;
    }
}

const many2one = registry.category("fields").get("many2one");
registry.category("fields").add("gdn_link_many2one", {
    ...many2one,
    component: GdnLinkMany2OneField,
});
