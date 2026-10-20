/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

function hasActiveDebugParam(params) {
    if (!params.has("debug")) {
        return false;
    }
    const value = params.get("debug");
    return ![null, "", "0", "false", "False"].includes(value);
}

async function stripDebugModeWhenBlocked() {
    const params = new URLSearchParams(window.location.search);
    if (!hasActiveDebugParam(params)) {
        return;
    }

    let blocked = false;
    try {
        blocked = await rpc(
            "/web/dataset/call_kw/permission.manager.policy/is_current_user_debug_blocked",
            {
                model: "permission.manager.policy",
                method: "is_current_user_debug_blocked",
                args: [],
                kwargs: {},
            }
        );
    } catch (error) {
        return;
    }

    if (!blocked) {
        return;
    }

    params.delete("debug");
    const query = params.toString();
    const cleanUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    window.location.replace(cleanUrl || "/web");
}

stripDebugModeWhenBlocked();
