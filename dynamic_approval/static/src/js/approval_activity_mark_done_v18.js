/** @odoo-module **/

import { Activity } from "@mail/core/web/activity";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

function getAssignedUserId(activity) {
    const rawUser = activity.user_id ?? activity.userId ?? activity.user;

    if (Array.isArray(rawUser)) {
        return Number(rawUser[0] || 0);
    }
    if (rawUser && typeof rawUser === "object") {
        return Number(rawUser.id || rawUser.userId || rawUser.user_id || 0);
    }
    return Number(rawUser || 0);
}

function isApprovalRequiredActivity(activity) {
    const summary = activity.summary ?? activity.display_name ?? "";
    return String(summary).startsWith("✅ Approval Required");
}

function isAdministrator() {
    return user.isSystem === true || user.isAdmin === true;
}

patch(Activity.prototype, {
    get professionalCanMarkDone() {
        const activity = this.props.activity;

        if (isAdministrator()) {
            return true;
        }

        // Pending Dynamic Approval activities must only be completed by
        // clicking Approve on the source document, never from the chatter.
        if (isApprovalRequiredActivity(activity)) {
            return false;
        }

        // Keep the existing rule for every normal activity.
        const assignedUserId = getAssignedUserId(activity);
        const currentUserId = Number(user.userId || user.user_id || 0);
        return assignedUserId > 0 && assignedUserId === currentUserId;
    },

    get professionalCanEditOrCancel() {
        if (isAdministrator()) {
            return true;
        }
        return !isApprovalRequiredActivity(this.props.activity);
    },
});
