/** @odoo-module **/

import { registry } from "@web/core/registry";
import { RPCError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { UncaughtPromiseError } from "@web/core/errors/error_service";

const PREFIX = "[PROFESSIONAL_APPROVAL_REQUIRED]";

function professionalApprovalRequiredHandler(env, error, originalError) {
    if (!(error instanceof UncaughtPromiseError) || !(originalError instanceof RPCError)) {
        return false;
    }
    const message = originalError?.data?.message || originalError?.message || "";
    if (!message.includes(PREFIX)) {
        return false;
    }
    if (error.unhandledRejectionEvent) {
        error.unhandledRejectionEvent.preventDefault();
    }
    const cleanMessage = message.replace(PREFIX, "").trim() || _t("Approval is required before continuing.");
    env.services.notification.add(cleanMessage, {
        title: _t("Approval Required"),
        type: "warning",
        sticky: true,
    });
    return true;
}

registry.category("error_handlers").add(
    "professionalApprovalRequiredHandler",
    professionalApprovalRequiredHandler,
    { sequence: 96 }
);
