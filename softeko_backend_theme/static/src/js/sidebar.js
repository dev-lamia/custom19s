/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

/**
 * A standalone Odoo 19 component. No patches to the standard navbar or
 * legacy web client APIs. Enabled per company at session start.
 */
export class SoftekoSidebar extends Component {
    static template = "softeko_backend_theme.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.ui = useState(useService("ui"));
        this.enabled = Boolean(session.softeko_theme?.sidebar);
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => this.render());
        onMounted(() => {
            if (this.enabled) {
                document.body.classList.add("softeko-sidebar-enabled");
            }
        });
        onWillUnmount(() => document.body.classList.remove("softeko-sidebar-enabled"));
    }

    get apps() {
        return this.menuService.getApps();
    }

    get activeAppId() {
        return this.menuService.getCurrentApp()?.id;
    }

    openApp(app) {
        return this.menuService.selectMenu(app);
    }
}

registry.category("main_components").add("softeko_backend_theme.sidebar", {
    Component: SoftekoSidebar,
});
