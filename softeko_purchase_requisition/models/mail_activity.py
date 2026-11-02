# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class MailActivity(models.Model):
    _inherit = "mail.activity"

    # -----------------------------
    # Helper: permission check
    # -----------------------------
    def _check_pr_activity_permission(self):
        # System/administrator workflow cleanup may intentionally use sudo.
        if self.env.su or self.env.user.has_group("base.group_system"):
            return

        for activity in self:
            if (
                activity.res_model == "softeko.purchase.requisition"
                and activity.user_id.id != self.env.user.id
            ):
                raise UserError(
                    _("Only the assigned user or an Administrator can modify this activity.")
                )

    def _get_pr_approval_action(self):
        """Return (PR, action_name, feedback) for true PR approval activities.

        Only the three dedicated approval-stage activities are converted from
        generic ``Mark Done`` into the corresponding business approval.
        Operational PR activities (RFQ creation/review, PO issue, requester
        review, etc.) keep Odoo's normal activity behaviour.
        """
        self.ensure_one()

        if self.res_model != "softeko.purchase.requisition" or not self.res_id:
            return False

        workflow_type = self.env.ref(
            "softeko_purchase_requisition.mail_activity_type_pr_workflow",
            raise_if_not_found=False,
        )
        if not workflow_type or self.activity_type_id != workflow_type:
            return False

        pr = self.env["softeko.purchase.requisition"].browse(self.res_id).exists()
        if not pr:
            return False

        summary = self.summary or ""

        manager_summary = _("Approve Purchase Requisition %s") % pr.name
        if pr.state == "submitted" and summary == manager_summary:
            return (
                pr,
                "action_manager_approve",
                _("Approved by Manager: %s") % self.env.user.name,
            )

        scm_summary = _("%s ready for SCM approval") % pr.name
        if pr.state == "rfq" and summary == scm_summary:
            return (
                pr,
                "action_mark_rfq_issued",
                _("Approved by SCM: %s") % self.env.user.name,
            )

        finance_summary = _("PR ready for Finance approval")
        if pr.state == "finance_approved" and summary == finance_summary:
            return (
                pr,
                "action_fd_approve",
                _("Approved by Finance: %s") % self.env.user.name,
            )

        return False

    # -----------------------------
    # Mark Done / approval bridge
    # -----------------------------
    def action_feedback(self, *args, **kwargs):
        self._check_pr_activity_permission()
        return super().action_feedback(*args, **kwargs)

    def action_done(self, *args, **kwargs):
        self._check_pr_activity_permission()
        return super().action_done(*args, **kwargs)

    def _action_done(self, feedback=False, attachment_ids=None):
        self._check_pr_activity_permission()

        # Do not convert automatic workflow cleanup into a business approval.
        #
        # ``pr_skip_activity_approval_bridge`` is used while an approval
        # action closes its own/peer activities (recursion protection).
        # ``pr_system_activity_cleanup`` is used by reset/cancel/stale-task
        # cleanup.  In both cases Odoo should only close the activity; it must
        # never execute Manager/SCM/Finance approval actions.
        if (
            self.env.context.get("pr_skip_activity_approval_bridge")
            or self.env.context.get("pr_system_activity_cleanup")
        ):
            return super()._action_done(
                feedback=feedback,
                attachment_ids=attachment_ids,
            )

        # Mark Done from the activity UI is normally a singleton operation.
        # Processing approval activities one-by-one also avoids a stage action
        # deleting duplicate approver activities that may be present in ``self``.
        if len(self) == 1:
            approval = self._get_pr_approval_action()
            if approval:
                pr, action_name, approval_feedback = approval
                activity_id = self.id

                # Execute exactly the same secured business method as the PR
                # Approve button.  The context tells _close_stage_activities()
                # that this activity is already being completed by the caller,
                # preventing recursion while still satisfying strict assignment.
                getattr(
                    pr.with_context(
                        pr_approval_activity_id=activity_id,
                        pr_skip_activity_approval_bridge=True,
                    ),
                    action_name,
                )()

                # The stage action intentionally removes duplicate activities
                # assigned to other configured approvers, but must leave this
                # activity for Odoo's normal completion path below.
                activity = self.exists()
                if not activity:
                    return False

                return super(MailActivity, activity)._action_done(
                    feedback=approval_feedback,
                    attachment_ids=attachment_ids,
                )

        return super()._action_done(
            feedback=feedback,
            attachment_ids=attachment_ids,
        )

    # -----------------------------
    # Block Cancel (Cancel = unlink)
    # -----------------------------
    def unlink(self):
        self._check_pr_activity_permission()
        return super().unlink()
