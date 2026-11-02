from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _professional_is_approval_required(self):
        """Return Dynamic Approval activities that must be closed via Approve."""
        return self.filtered(
            lambda activity: (activity.summary or "").startswith(
                "✅ Approval Required"
            )
        )

    def _professional_is_administrator(self):
        return self.env.su or self.env.user.has_group("base.group_system")

    def _professional_check_mark_done_access(self):
        """Protect chatter completion without affecting normal approval flow."""
        if self._professional_is_administrator():
            return

        if self._professional_is_approval_required():
            raise AccessError(
                _(
                    "This approval activity cannot be marked as done from "
                    "the chatter. Open the document and use the Approve button."
                )
            )

        restricted = self.filtered(
            lambda activity: activity.user_id != self.env.user
        )
        if restricted:
            raise AccessError(
                _(
                    "Only the user assigned to this activity or an "
                    "Administrator can mark it as done."
                )
            )

    def _professional_check_approval_activity_manage_access(self):
        """Block manual Edit/Cancel of pending approval chatter activities."""
        if self._professional_is_administrator():
            return

        if self._professional_is_approval_required():
            raise AccessError(
                _(
                    "Approval Required activities cannot be edited or cancelled "
                    "from the chatter. Use the approval workflow on the document."
                )
            )

    def write(self, vals):
        self._professional_check_approval_activity_manage_access()
        return super().write(vals)

    def unlink(self):
        self._professional_check_approval_activity_manage_access()
        return super().unlink()

    def action_feedback(self, feedback=False, attachment_ids=None):
        self._professional_check_mark_done_access()
        return super().action_feedback(
            feedback=feedback,
            attachment_ids=attachment_ids,
        )

    def action_feedback_schedule_next(self, feedback=False, attachment_ids=None):
        self._professional_check_mark_done_access()
        return super().action_feedback_schedule_next(
            feedback=feedback,
            attachment_ids=attachment_ids,
        )

    def action_done(self):
        self._professional_check_mark_done_access()
        return super().action_done()

    def _action_done(self, feedback=False, attachment_ids=False):
        """Protect the low-level completion path used by Odoo chatter."""
        self._professional_check_mark_done_access()
        return super()._action_done(
            feedback=feedback,
            attachment_ids=attachment_ids,
        )

    def _professional_source_action(self):
        """Open the business document linked to an approval activity."""
        self.ensure_one()

        source_model = self.res_model
        source_id = self.res_id

        if source_model == "professional.approval.request" and source_id:
            request = self.env[source_model].sudo().browse(source_id).exists()
            if request:
                source_model = request.source_model
                source_id = request.source_id

        if not source_model or not source_id:
            return False

        record = self.env[source_model].sudo().browse(source_id).exists()
        if not record:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": record.display_name or _("Source Document"),
            "res_model": source_model,
            "res_id": source_id,
            "view_mode": "form",
            "target": "current",
        }

    def professional_open_source_document(self):
        """Return the full business document for approval activities."""
        self.ensure_one()
        if (self.summary or "").startswith("✅ Approval Required"):
            action = self._professional_source_action()
            if action:
                return action
        return False

    def action_open_document(self):
        """Open the source form directly for Dynamic Approval activities."""
        self.ensure_one()
        if (self.summary or "").startswith("✅ Approval Required"):
            action = self._professional_source_action()
            if action:
                return action
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def get_formview_action(self, access_uid=None):
        """Redirect approval activity rows to their full source document."""
        self.ensure_one()
        if (self.summary or "").startswith("✅ Approval Required"):
            action = self._professional_source_action()
            if action:
                return action
        return super().get_formview_action(access_uid=access_uid)
