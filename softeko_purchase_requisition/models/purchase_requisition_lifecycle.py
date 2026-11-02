# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


CONFIRMED_PO_STATES = ("purchase",)


class PurchaseRequisition(models.Model):
    _inherit = "softeko.purchase.requisition"

    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="RFQs / Purchase Orders",
        compute="_compute_purchase_order_ids",
        search="_search_purchase_order_ids",
        compute_sudo=True,
        readonly=True,
    )
    active_purchase_order_ids = fields.Many2many(
        "purchase.order",
        "pr_active_purchase_order_compute_rel",
        "requisition_id",
        "purchase_order_id",
        string="Active RFQs / Purchase Orders",
        compute="_compute_purchase_order_ids",
        compute_sudo=True,
        readonly=True,
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Products",
        compute="_compute_product_ids",
        search="_search_product_ids",
    )
    stakeholder_user_ids = fields.Many2many(
        "res.users",
        "pr_stakeholder_user_rel",
        "requisition_id",
        "user_id",
        string="Workflow Stakeholders",
        copy=False,
        help="Users who actually participated in or were assigned a stage of this PR. Used for continued read access and lifecycle notifications; chatter remains the audit history.",
    )

    reset_requested = fields.Boolean(string="Reset Requested", copy=False, tracking=True)
    reset_requested_by_id = fields.Many2one("res.users", string="Reset Requested By", copy=False, readonly=True)
    reset_requested_on = fields.Datetime(string="Reset Requested On", copy=False, readonly=True)
    reset_blocking_po_ids = fields.Many2many(
        "purchase.order",
        "pr_reset_blocking_po_rel",
        "requisition_id",
        "purchase_order_id",
        string="POs Blocking Reset",
        copy=False,
    )
    reset_ready = fields.Boolean(compute="_compute_request_flags")

    cancel_requested = fields.Boolean(string="Cancel Requested", copy=False, tracking=True)
    cancel_requested_by_id = fields.Many2one("res.users", string="Cancel Requested By", copy=False, readonly=True)
    cancel_requested_on = fields.Datetime(string="Cancel Requested On", copy=False, readonly=True)
    cancel_blocking_po_ids = fields.Many2many(
        "purchase.order",
        "pr_cancel_blocking_po_rel",
        "requisition_id",
        "purchase_order_id",
        string="RFQs/POs Blocking Cancellation",
        copy=False,
    )

    rfq_review_required = fields.Boolean(
        string="RFQ Review Required",
        copy=False,
        tracking=True,
        help="Set after a reset when active RFQs are already linked. RFQ Create users must review the synchronized RFQ(s) and explicitly send the PR for SCM approval.",
    )

    can_request_reset = fields.Boolean(compute="_compute_request_flags")
    can_request_cancel = fields.Boolean(compute="_compute_request_flags")
    can_finalize_reset = fields.Boolean(compute="_compute_request_flags")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.sudo()._register_stakeholders(rec.requester_id)
        return records

    def _register_stakeholders(self, users):
        users = users.filtered(lambda u: u and not u.share)
        if not users:
            return
        for rec in self:
            missing = users - rec.stakeholder_user_ids
            if missing:
                rec.sudo().write({"stakeholder_user_ids": [(4, user.id) for user in missing]})

    def _schedule_pr_activity(self, activity_type_id, user_id, summary, note=False):
        # All PR workflow activities use a dedicated activity type.  This
        # distinguishes them from manual To-Dos without adding a stored column
        # to the global mail.activity table.
        workflow_type = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        activity = super()._schedule_pr_activity(workflow_type.id, user_id, summary, note=note)
        user = self.env["res.users"].sudo().browse(user_id)
        self._register_stakeholders(user)
        return activity

    @api.depends("material_line_ids.product_id")
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = rec.material_line_ids.filtered(lambda l: not l.display_type).mapped("product_id")

    def _search_product_ids(self, operator, value):
        domain = [("product_id", operator, value)]
        lines = self.env["softeko.purchase.requisition.line"].sudo().search(domain)
        return [("id", "in", lines.mapped("pr_requisition_id").ids)]

    def _search_purchase_order_ids(self, operator, value):
        """Search PRs through linked RFQ/POs, including Odoo 19 ``any`` domains.

        A relational search such as ``('purchase_order_ids', 'ilike', text)``
        is optimized by Odoo 19 into an ``any``/``any!`` condition whose value
        is a purchase.order domain.  Forwarding ``any`` to purchase.order.name
        produces ``Cannot use 'any' with non-relational fields``.
        """
        PO = self.env["purchase.order"].sudo()

        if operator in ("any", "any!"):
            orders = PO.search(value or [])
            prs = orders.mapped("pr_requisition_id") | orders.mapped("pr_requisition_ids")
            return [("id", "in", prs.ids)]

        if operator in ("not any", "not any!"):
            orders = PO.search(value or [])
            prs = orders.mapped("pr_requisition_id") | orders.mapped("pr_requisition_ids")
            return [("id", "not in", prs.ids)]

        if operator in ("=", "!=") and not value:
            linked = PO.search(["|",
                ("pr_requisition_id", "!=", False),
                ("pr_requisition_ids", "!=", False),
            ])
            prs = linked.mapped("pr_requisition_id") | linked.mapped("pr_requisition_ids")
            return [("id", "not in" if operator == "=" else "in", prs.ids)]

        if operator in ("in", "not in") and isinstance(value, (list, tuple)):
            orders = PO.browse(value)
        elif operator in ("=", "!=") and isinstance(value, int):
            orders = PO.browse([value])
        else:
            # Text search requested directly against the computed relation.
            # Restrict the delegated operator to operators valid for Char name.
            text_operator = operator if operator in ("=", "!=", "like", "not like", "ilike", "not ilike", "=like", "=ilike") else "ilike"
            orders = PO.search([("name", text_operator, value)])

        prs = orders.mapped("pr_requisition_id") | orders.mapped("pr_requisition_ids")
        return [("id", "not in" if operator in ("!=", "not in", "not like", "not ilike") else "in", prs.ids)]

    def _get_purchase_order_domain(self, include_cancelled=True):
        self.ensure_one()
        domain = ["|", ("pr_requisition_id", "=", self.id), ("pr_requisition_ids", "in", self.id)]
        if not include_cancelled:
            domain = [("state", "!=", "cancel")] + domain
        return domain

    def _compute_purchase_order_ids(self):
        PO = self.env["purchase.order"].sudo()
        for rec in self:
            if not rec.id:
                rec.purchase_order_ids = False
                rec.active_purchase_order_ids = False
                continue
            all_orders = PO.search([
                "|",
                ("pr_requisition_id", "=", rec.id),
                ("pr_requisition_ids", "in", rec.id),
            ])
            rec.purchase_order_ids = all_orders
            rec.active_purchase_order_ids = all_orders.filtered(lambda po: po.state != "cancel")

    @api.depends("purchase_order_ids.state")
    def _compute_rfq_info(self):
        for rec in self:
            active = rec.purchase_order_ids.filtered(lambda po: po.state != "cancel")
            rec.rfq_count = len(active)
            rec.rfq_created = bool(active)

    @api.depends(
        "reset_requested", "reset_requested_by_id", "cancel_requested", "reset_blocking_po_ids.state",
        "requester_id", "company_id", "state", "stakeholder_user_ids", "from_office_supply",
    )
    def _compute_request_flags(self):
        user = self.env.user
        for rec in self:
            authorized = rec._is_lifecycle_stakeholder(user)
            # Cancelled normal PRs may be reopened through the same controlled Reset to Draft flow.
            # Cancelled Office Supply PRs are intentionally final because cancellation returns the
            # source Office Supply request to its own workflow and clears the old PR link.
            office_supply_cancelled = rec.from_office_supply and rec.state == "canceled"
            rec.can_request_reset = authorized and rec.state != "draft" and not office_supply_cancelled and not rec.reset_requested and not rec.cancel_requested
            rec.can_request_cancel = authorized and rec.state != "canceled" and not rec.cancel_requested and not rec.reset_requested
            reset_blockers = rec.sudo().reset_blocking_po_ids
            rec.reset_ready = bool(rec.reset_requested) and all(
                po.state == "draft" for po in reset_blockers
            )
            # The stakeholder who initiated the reset should be able to carry it through
            # after blocking POs are returned to Draft.  The requester is also allowed as a
            # safe fallback, and administrators can always recover the workflow.
            rec.can_finalize_reset = rec.reset_ready and (
                user.has_group("base.group_system")
                or rec.reset_requested_by_id == user
                or rec.requester_id == user
            )

    def _is_lifecycle_stakeholder(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group("base.group_system") or user == self.requester_id or user in self.stakeholder_user_ids:
            return True
        if self._get_requester_manager_user() == user:
            return True
        cfg = self._get_approval_config()
        return user in (cfg.link_user_ids | cfg.scm_approver_ids | cfg.finance_user_ids | cfg.po_user_ids)

    def _stakeholder_users(self):
        self.ensure_one()
        users = (self.stakeholder_user_ids | self.requester_id).filtered(lambda u: not u.share)
        # Legacy PRs upgraded from pre-19.0.0.3.0 may not have participant records yet.
        # Use reached-stage configuration only as a fallback for those old records.
        if len(users) > 1:
            return users

        cfg = self._get_approval_config()
        if self.from_office_supply:
            if self.state in ("finance_approved", "sale_order", "po_issued", "done"):
                users |= cfg.finance_user_ids
            if self.state in ("po_issued", "done"):
                users |= cfg.po_user_ids
            return users.filtered(lambda u: not u.share)

        manager = self._get_requester_manager_user()
        stage_rank = {
            "draft": 0, "submitted": 1, "rfq": 2, "finance_approved": 3,
            "sale_order": 4, "po_issued": 5, "done": 6, "canceled": 6,
        }.get(self.state, 0)
        if manager and stage_rank >= 1:
            users |= manager
        if stage_rank >= 2:
            users |= cfg.link_user_ids | cfg.scm_approver_ids
        if stage_rank >= 3:
            users |= cfg.finance_user_ids
        if stage_rank >= 5:
            users |= cfg.po_user_ids
        return users.filtered(lambda u: not u.share)

    def _check_office_supply_lifecycle_allowed(self, action="change"):
        self.ensure_one()
        if not self.from_office_supply or not self.env.registry.get("office.supply.assignment"):
            return
        assignment = self.env["office.supply.assignment"].sudo().search([
            ("purchase_pr_requisition_id", "=", self.id)
        ], limit=1)
        if not assignment:
            return
        if assignment.state == "assigned":
            raise UserError(_(
                "This Office Supply request is already assigned/fulfilled. "
                "The linked Purchase Requisition cannot be reset or cancelled."
            ))
        if action in ("reset", "submit") and assignment.state == "cancel":
            raise UserError(_(
                "The source Office Supply request is cancelled. This Purchase Requisition cannot be reset/resubmitted; "
                "cancel the PR as well if procurement is no longer required."
            ))

    def _notify_users(self, users, body):
        """Post a normal chatter message and notify the supplied users.

        Keep this helper for workflow notices where a thread message is intended.
        Reset-to-Draft role routing uses ``_notify_users_direct`` instead so
        follower subscriptions cannot widen the recipient list.
        """
        self.ensure_one()
        partners = users.mapped("partner_id").filtered(lambda p: p)
        if not partners:
            return self.env["mail.message"]
        return self.message_post(
            body=body,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_note",
        )

    def _notify_users_direct(self, users, body, *, exclude_users=None, subject=None):
        """Notify only explicit users, without notifying PR followers.

        Odoo 19 ``message_post`` is a thread message and its notification
        recipient computation can include followers.  Reset notifications have
        strict business recipients, so use ``message_notify`` with
        ``notify_skip_followers=True``.  The reset actor is also removed from
        the explicit recipient set before the notification is created.

        ``message_notify`` creates a ``user_notification`` message, therefore
        the role-specific mail does not add duplicate visible chatter entries;
        the separate reset audit note remains the single chatter history item.
        """
        self.ensure_one()
        users = users.filtered(lambda u: u and not u.share)
        if exclude_users:
            exclude_ids = set(exclude_users.ids)
            users = users.filtered(lambda u: u.id not in exclude_ids)
        partners = users.mapped("partner_id").filtered(lambda p: p)
        if not partners:
            return self.env["mail.message"]

        return self.with_context(
            mail_notify_author=False,
            mail_notify_author_mention=False,
            mail_post_autofollow=False,
        ).message_notify(
            body=body,
            subject=subject,
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_note",
            notify_author=False,
            notify_author_mention=False,
            notify_skip_followers=True,
        )

    def _open_change_request_wizard(self, action_type):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reset to Draft") if action_type == "reset" else _("Cancel Purchase Requisition"),
            "res_model": "softeko.purchase.requisition.change.request.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("softeko_purchase_requisition.view_softeko_purchase_requisition_change_request_wizard_form").id,
            "target": "new",
            "context": {
                "default_requisition_id": self.id,
                "default_action_type": action_type,
            },
        }

    def action_open_reset_wizard(self):
        self.ensure_one()
        if not self.can_request_reset:
            raise UserError(_("You are not allowed to request a reset for this requisition at its current stage."))
        return self._open_change_request_wizard("reset")

    def action_open_cancel_wizard(self):
        self.ensure_one()
        if not self.can_request_cancel:
            raise UserError(_("You are not allowed to cancel this requisition at its current stage."))
        return self._open_change_request_wizard("cancel")

    def action_cancel(self):
        return self.action_open_cancel_wizard()

    def action_request_reset(self, reason):
        self.ensure_one()
        self._check_office_supply_lifecycle_allowed(action="reset")
        if not self._is_lifecycle_stakeholder():
            raise UserError(_("You are not allowed to request this reset."))
        if self.state == "draft":
            raise UserError(_("This requisition is already in Draft."))
        if self.from_office_supply and self.state == "canceled":
            raise UserError(_(
                "A cancelled Office Supply PR cannot be reopened because its source Office Supply request "
                "was returned to the Office Supply workflow. Continue from that source request instead."
            ))
        if self.reset_requested or self.cancel_requested:
            raise UserError(_("A reset or cancellation request is already pending."))

        # Office Supply PRs at Finance have not reached PO creation yet.  Do not
        # touch purchase.order here: the Office Supply requester may intentionally
        # have no Purchase/Accounting access and must still be able to reset their
        # own PR back to Draft.
        if self.from_office_supply and self.state == "finance_approved":
            blockers = self.env["purchase.order"].browse()
        else:
            blockers = self.sudo().purchase_order_ids.filtered(lambda po: po.state in CONFIRMED_PO_STATES)

        if blockers:
            # A blocking confirmed PO creates a real pending-reset state, so keep
            # a separate request audit event. Immediate resets skip this request
            # message and log only the completed reset below.
            self.message_post(
                body=Markup(_(
                    "<b>Reset to Draft requested</b><br/>Requested by: %(user)s<br/>Reason: %(reason)s"
                )) % {
                    "user": self.env.user.display_name,
                    "reason": reason,
                },
                notify_skip_followers=True,
            )
            # Internal lifecycle bookkeeping may reference Purchase Orders that
            # the requester cannot read directly. Authorization was already
            # checked above, so use sudo only for this controlled state update.
            self.sudo().with_context(mail_notrack=True).write({
                "reset_requested": True,
                "reset_requested_by_id": self.env.user.id,
                "reset_requested_on": fields.Datetime.now(),
                "reset_blocking_po_ids": [(6, 0, blockers.ids)],
            })
            self._create_po_reset_activities(blockers)
            return {"type": "ir.actions.client", "tag": "reload"}

        # Draft/Sent/To Approve RFQs do not block reset. Keep their document links for review after resubmit.
        self._perform_reset_to_draft(reason=reason, immediate=True)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _create_po_reset_activities(self, blockers):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        cfg = self._get_approval_config()
        users = cfg.po_user_ids.filtered(lambda u: not u.share)
        if not users:
            raise UserError(_("No PO Issuer is configured for company %s.") % self.company_id.display_name)
        names = ", ".join(blockers.mapped("name"))
        shared = blockers.filtered(lambda po: bool(po._get_all_pr_requisitions() - self))
        shared_note = ""
        if shared:
            shared_note = _(" Shared confirmed PO(s) %(pos)s also contain other PRs; do not blindly cancel/reset them. Split/amend the PO or coordinate reset of all affected PRs first.") % {"pos": ", ".join(shared.mapped("name"))}
        for user in users:
            summary = _("Reset PO(s) to Draft for %s") % self.name
            existing = self.activity_ids.sudo().filtered(lambda a: a.user_id == user and a.summary == summary)
            if not existing:
                self._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=_("Resolve the following confirmed PO(s) through Odoo's standard purchase controls and return the PR-related dependency to Draft: %(pos)s.%(shared)s") % {"pos": names, "shared": shared_note},
                )
        self._notify_users(users, _("Reset requested for %s. Confirmed PO(s) must be reset to Draft first: %s") % (self.name, names))

    def _check_reset_dependencies(self):
        for rec in self.filtered("reset_requested"):
            blockers = rec.sudo().reset_blocking_po_ids
            if blockers and all(po.state == "draft" for po in blockers):
                summary = _("Complete Reset to Draft for %s") % rec.name
                # The person who asked for the reset owns the final reset step.  Falling back
                # to the requester prevents old/legacy pending resets from becoming orphaned.
                completion_user = rec.reset_requested_by_id or rec.requester_id
                if completion_user:
                    existing = rec.activity_ids.sudo().filtered(
                        lambda a: a.user_id == completion_user and a.summary == summary
                    )
                    if not existing:
                        rec._schedule_pr_activity(
                            activity_type_id=self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow").id,
                            user_id=completion_user.id,
                            summary=summary,
                            note=_("All blocking Purchase Orders are back in Draft. Complete the PR reset."),
                        )
                        rec._notify_users(
                            completion_user,
                            _("All blocking Purchase Orders for %s are now Draft. You can complete the PR reset.") % rec.name,
                        )

    def action_finalize_reset(self):
        self.ensure_one()
        allowed_users = (self.reset_requested_by_id | self.requester_id).filtered(lambda u: u)
        if self.env.user not in allowed_users and not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only the reset initiator or the requisition requester can complete the final reset."))
        if not self.reset_requested:
            raise UserError(_("There is no reset request pending."))
        blockers = self.sudo().reset_blocking_po_ids
        if any(po.state != "draft" for po in blockers):
            raise UserError(_("All blocking Purchase Orders must be in Draft before the PR can be reset."))
        self._perform_reset_to_draft(reason=_("Confirmed PO reset completed"), immediate=False)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _perform_reset_to_draft(self, reason, immediate=False):
        self.ensure_one()
        old_state = self.state
        reset_by = self.env.user
        requested_by = self.reset_requested_by_id
        # Always initialise the RFQ set. Office Supply PRs go directly from
        # Draft to Finance and therefore have no SCM/RFQ link at this stage.
        # Keeping this empty for that branch prevents both RFQ review logic and
        # any later reference to an uninitialised local variable.
        open_rfqs = self.env["purchase.order"].browse()
        # An Office Supply PR being reset from Finance has not reached PO
        # creation.  Skip purchase.order entirely so its requester does not need
        # Purchase/Accounting rights just to reset their own requisition.
        if self.from_office_supply and old_state == "finance_approved":
            rfq_review_required = False
        else:
            linked_orders = self.sudo().purchase_order_ids
            open_rfqs = linked_orders.filtered(lambda po: po.state in ("draft", "sent", "to approve"))
            # If a confirmed PO was reset first, it is Draft now and must also be reviewed by the RFQ Create team.
            if not open_rfqs:
                open_rfqs = linked_orders.filtered(lambda po: po.state == "draft")
            rfq_review_required = bool(open_rfqs)

        self._close_lifecycle_activities(_("Closed because %s was reset to Draft.") % self.name)
        # The explicit audit note below is the authoritative reset history.
        # Suppress automatic tracked-field chatter/notifications for this internal
        # state write so reset communication cannot leak through follower tracking.
        self.sudo().with_context(skip_pr_lifecycle_checks=True, mail_notrack=True).write({
            "state": "draft",
            "reset_requested": False,
            "reset_requested_by_id": False,
            "reset_requested_on": False,
            "reset_blocking_po_ids": [(5, 0, 0)],
            "rfq_review_required": rfq_review_required,
        })

        requested_by_line = Markup("")
        if requested_by and requested_by != reset_by:
            requested_by_line = Markup(_("<br/>Reset requested by: %s")) % requested_by.display_name
        body = Markup(_(
            "<b>Purchase Requisition reset to Draft</b><br/>"
            "Reset by: %(user)s%(requested_by)s<br/>"
            "Previous stage: %(stage)s<br/>"
            "Reason: %(reason)s"
        )) % {
            "user": reset_by.display_name,
            "requested_by": requested_by_line,
            "stage": dict(self._fields["state"].selection).get(old_state, old_state),
            "reason": reason,
        }
        # Keep one visible audit entry in chatter, but never use the audit note
        # itself as an email/inbox notification to followers.
        self.message_post(body=body, notify_skip_followers=True)

        # Reset notification routing is role-based, not actor-based.
        #
        # 1) The PR requester owns the amendment/resubmission follow-up.
        # 2) Only users explicitly configured in Approval Setup > RFQ Link receive
        #    the linked-RFQ review notification.
        # 3) The user who completed the reset is excluded from both directed
        #    notifications/activities because they already know about their action.
        #
        # The reset actor is still recorded in the chatter audit note above.
        requester_recipient = self.requester_id.filtered(lambda u: u.id != reset_by.id)
        if requester_recipient:
            requester_body = _("%(pr)s was reset to Draft by %(user)s. Please review/amend the requisition and resubmit it when ready.") % {
                "pr": self.name,
                "user": reset_by.display_name,
            }
            self._notify_users_direct(
                requester_recipient,
                requester_body,
                exclude_users=reset_by,
                subject=_("Purchase Requisition reset to Draft"),
            )

            review_summary = _("Requisition Review")
            existing_review = self.activity_ids.sudo().filtered(
                lambda a: a.user_id == requester_recipient
                and a.summary == review_summary
                and a.activity_type_id == self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
            )
            if not existing_review:
                self._schedule_pr_activity(
                    activity_type_id=self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow").id,
                    user_id=requester_recipient.id,
                    summary=review_summary,
                    note=Markup(_(
                        "<b>Purchase Requisition reset to Draft</b><br/>"
                        "Reset by: %(user)s<br/>"
                        "Previous stage: %(stage)s<br/>"
                        "Reason: %(reason)s<br/><br/>"
                        "Review/amend the requisition and resubmit it when ready."
                    )) % {
                        "user": reset_by.display_name,
                        "stage": dict(self._fields["state"].selection).get(old_state, old_state),
                        "reason": reason,
                    },
                )

        if open_rfqs:
            cfg = self._get_approval_config()
            rfq_users = cfg.link_user_ids.filtered(lambda u: not u.share and u.id != reset_by.id)
            if rfq_users:
                self._notify_users_direct(
                    rfq_users,
                    _("%(pr)s was reset to Draft by %(user)s and may be amended. After resubmission, review the linked RFQ(s) before sending the PR for SCM approval.") % {
                        "pr": self.name,
                        "user": reset_by.display_name,
                    },
                    exclude_users=reset_by,
                    subject=_("Purchase Requisition RFQ review required"),
                )

    def action_request_cancel(self, reason):
        self.ensure_one()
        self._check_office_supply_lifecycle_allowed(action="cancel")
        if not self._is_lifecycle_stakeholder():
            raise UserError(_("You are not allowed to request cancellation."))
        if self.state == "canceled":
            raise UserError(_("This requisition is already cancelled."))
        if self.reset_requested or self.cancel_requested:
            raise UserError(_("A reset or cancellation request is already pending."))

        # Linked RFQ/PO dependencies are internal lifecycle bookkeeping.  A PR
        # requester is intentionally allowed to cancel without Purchase access,
        # so inspect them under sudo after stakeholder authorization above.
        blockers = self.sudo().purchase_order_ids.filtered(
            lambda po: po.state != "cancel" and self._pr_still_affects_order(po)
        )
        self.message_post(body=Markup(_(
            "<b>Cancellation requested</b><br/>Requested by: %(user)s<br/>Reason: %(reason)s"
        )) % {
            "user": self.env.user.display_name,
            "reason": reason,
        })
        if not blockers:
            self._finalize_cancellation(reason)
            return {"type": "ir.actions.client", "tag": "reload"}

        # The requester may not have purchase.order read rights.  Authorization
        # has already been checked, therefore store the technical dependency
        # relation under sudo just like Reset to Draft does.
        self.sudo().with_context(mail_notrack=True).write({
            "cancel_requested": True,
            "cancel_requested_by_id": self.env.user.id,
            "cancel_requested_on": fields.Datetime.now(),
            "cancel_blocking_po_ids": [(6, 0, blockers.ids)],
        })
        self._create_cancel_dependency_activities(blockers)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _pr_still_affects_order(self, order):
        self.ensure_one()
        return self in order._get_linked_requisitions()

    def _create_cancel_dependency_activities(self, blockers):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        draft_rfqs = blockers.filtered(lambda po: po.state in ("draft", "sent", "to approve"))
        confirmed = blockers.filtered(lambda po: po.state in CONFIRMED_PO_STATES)
        if draft_rfqs:
            users = self._rfq_responsible_users(draft_rfqs)
            for user in users:
                summary = _("Cancel/Remove RFQ allocation for %s") % self.name
                if not self.activity_ids.sudo().filtered(lambda a: a.user_id == user and a.summary == summary):
                    self._schedule_pr_activity(
                        activity_type_id=ActivityType.id,
                        user_id=user.id,
                        summary=summary,
                        note=_("Cancel the linked RFQ(s), or unlink only this PR from a shared RFQ."),
                    )
        if confirmed:
            users = self._get_approval_config().po_user_ids.filtered(lambda u: not u.share)
            for user in users:
                summary = _("Cancel/Resolve PO dependency for %s") % self.name
                if not self.activity_ids.sudo().filtered(lambda a: a.user_id == user and a.summary == summary):
                    self._schedule_pr_activity(
                        activity_type_id=ActivityType.id,
                        user_id=user.id,
                        summary=summary,
                        note=_("Resolve confirmed PO dependency using Odoo's normal purchase flow. Shared POs must be split/amended so other PRs are not affected."),
                    )

    def _check_cancel_dependencies(self):
        for rec in self.filtered("cancel_requested"):
            uncleared = rec.sudo().cancel_blocking_po_ids.filtered(
                lambda po: po.state != "cancel" and rec._pr_still_affects_order(po)
            )
            if not uncleared:
                rec._finalize_cancellation(_("All RFQ/PO dependencies were cleared."))

    def _finalize_cancellation(self, reason):
        self.ensure_one()
        self._close_lifecycle_activities(_("Closed because %s was cancelled.") % self.name)
        stakeholders = self._stakeholder_users()
        # Cancellation is already explicitly authorized before reaching this
        # helper.  Clear internal purchase.order relations under sudo so a normal
        # requester does not need Purchase ACLs merely to cancel their own PR.
        self.sudo().with_context(
            skip_pr_lifecycle_checks=True,
            mail_notrack=True,
        ).write({
            "state": "canceled",
            "cancel_requested": False,
            "cancel_requested_by_id": False,
            "cancel_requested_on": False,
            "cancel_blocking_po_ids": [(5, 0, 0)],
            "rfq_review_required": False,
        })
        self._notify_users(stakeholders, _("Purchase Requisition %s has been cancelled. %s") % (self.name, reason))
        self._sync_office_supply_after_pr_cancel()

    def _close_lifecycle_activities(self, feedback):
        """Close PR workflow activities as lifecycle cleanup, never approval.

        Reset/cancel operations may close Manager, SCM or Finance approval
        activities.  Those closures are administrative workflow cleanup and
        must not be interpreted by ``mail.activity`` as the assignee approving
        the PR.  Complete them with an explicit cleanup context so the chatter
        keeps the assignment/completion audit trail without triggering a stage
        transition.
        """
        workflow_type = self.env.ref(
            "softeko_purchase_requisition.mail_activity_type_pr_workflow"
        )
        activities = self.activity_ids.sudo().filtered(
            lambda a: a.activity_type_id == workflow_type
        )
        if activities:
            activities.with_context(
                pr_system_activity_cleanup=True,
                pr_skip_activity_approval_bridge=True,
            ).action_feedback(feedback)

    def _rfq_responsible_users(self, orders):
        # Always include configured RFQ Create users. The document buyer alone is not
        # enough after a PR reset because PR assigns the review responsibility to the group.
        users = orders.mapped("user_id") | self._get_approval_config().link_user_ids
        return users.filtered(lambda u: not u.share)

    def _sync_office_supply_after_pr_cancel(self):
        self.ensure_one()
        if not self.from_office_supply or not self.env.registry.get("office.supply.assignment"):
            return
        assignments = self.env["office.supply.assignment"].sudo().search([
            ("purchase_pr_requisition_id", "=", self.id)
        ])
        for assignment in assignments:
            if assignment.state == "assigned":
                # Fulfilled office supplies must not be silently rewound.
                continue
            if assignment.state == "cancel":
                assignment.message_post(body=_("Linked Purchase Requisition %s was cancelled. The Office Supply request remains Cancelled.") % self.name)
                assignment.write({"purchase_pr_requisition_id": False})
                continue
            assignment.message_post(body=_("Linked Purchase Requisition %s was cancelled. The request is returned to Manager Approved for replenishment review.") % self.name)
            assignment.write({
                "state": "manager_approved",
                "purchase_pr_requisition_id": False,
            })
            if hasattr(assignment, "_schedule_inventory_activity"):
                assignment._schedule_inventory_activity()

    def _check_no_pending_lifecycle_request(self):
        for rec in self:
            if rec.reset_requested:
                raise UserError(_("A Reset to Draft request is pending for %s. Complete or resolve it before continuing the normal workflow.") % rec.name)
            if rec.cancel_requested:
                raise UserError(_("A cancellation request is pending for %s. Resolve the linked RFQ/PO dependencies before continuing the normal workflow.") % rec.name)

    def action_manager_approve(self):
        self._check_no_pending_lifecycle_request()
        return super().action_manager_approve()

    def action_manager_review(self):
        self._check_no_pending_lifecycle_request()
        return super().action_manager_review()

    def action_fd_approve(self):
        self._check_no_pending_lifecycle_request()
        return super().action_fd_approve()

    def action_fd_review(self):
        self._check_no_pending_lifecycle_request()
        if self.filtered("from_office_supply"):
            raise UserError(_(
                "Send Back is not used for Office Supply requisitions. "
                "Use Reset to Draft instead so the requisition returns to the Office Supply requester."
            ))
        return super().action_fd_review()

    def _check_sale_order_confirmation(self):
        self._check_no_pending_lifecycle_request()
        return super()._check_sale_order_confirmation()

    def action_manager_refuse(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted requisitions can be refused by the manager."))
            if not rec.is_manager:
                raise UserError(_("Only the requester's manager can refuse at this stage."))
            rec.action_request_cancel(_("Refused by Manager: %s") % self.env.user.display_name)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_fd_refuse(self):
        self._check_finance_access()
        for rec in self:
            if rec.state != "finance_approved":
                raise UserError(_("Only Finance-stage requisitions can be refused by Finance."))
            rec.action_request_cancel(_("Refused by Finance: %s") % self.env.user.display_name)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_submit(self):
        for rec in self:
            if rec.requester_id != self.env.user and not self.env.user.has_group("base.group_system"):
                raise UserError(_("Only the requester can submit this requisition."))
            if rec.state != "draft":
                raise UserError(_("Only requisitions in Draft can be submitted."))
            if not rec.material_line_ids.filtered(lambda line: not line.display_type):
                raise UserError(_("Please add at least one product line before submitting."))

            rec._sync_company_from_sale_order()
            if rec.from_office_supply:
                rec._check_office_supply_lifecycle_allowed(action="submit")
            rec._close_review_activity_for_requester()
            if rec.from_office_supply:
                rec._validate_finance_config()
                rec.state = "finance_approved"
                rec._create_finance_activities()
                rec.message_post(body=_("Office Supply PR resubmitted directly to Finance Approval after reset."))
            else:
                if rec._requester_skips_manager_approval():
                    # Senior employees configured for this PR company do not
                    # require Manager Approval.  Move them to the same RFQ/PO
                    # stage reached after a normal manager approval.
                    rec._validate_po_link_config()
                    rec._validate_scm_approver_config()
                    rec.state = "rfq"

                    if rec.rfq_created and rec.rfq_review_required:
                        rec._create_rfq_recheck_activities()
                    elif rec.rfq_created:
                        rec._approve_scm_activities()
                    else:
                        rec._create_po_link_activities()

                    rec.message_post(
                        body=_(
                            "Manager Approval bypassed for %s based on the "
                            "company Approval Configuration."
                        ) % rec.requester_id.display_name
                    )
                else:
                    rec._validate_requester_manager_exists()
                    rec.state = "submitted"
                    rec._create_manager_approval_activity()

    def _create_rfq_recheck_activities(self):
        """Ask RFQ Create users to review already-linked RFQs after a PR reset."""
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        for rec in self:
            users = rec._get_approval_config().link_user_ids.filtered(lambda u: not u.share)
            if not users:
                raise UserError(_("No RFQ Create user is configured for company %s.") % rec.company_id.display_name)
            summary = _("Review linked RFQ(s) after reset for %s") % rec.name
            created_any = False
            for user in users:
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id == ActivityType
                    and a.user_id == user
                    and a.summary == summary
                )
                if not existing:
                    rec._schedule_pr_activity(
                        activity_type_id=ActivityType.id,
                        user_id=user.id,
                        summary=summary,
                        note=_(
                            "This PR was reset and resubmitted while RFQ(s) are already linked. "
                            "Review the linked RFQ document(s), then use 'Send for Approval' on the PR. "
                            "No PR-to-RFQ line synchronization or quantity matching is performed."
                        ),
                    )
                    created_any = True
            if created_any:
                rec._notify_users(
                    users,
                    _("%s has been resubmitted after Reset to Draft. Review the linked RFQ(s), then send the PR for approval.") % rec.name,
                )

    def action_complete_rfq_review(self):
        self._check_no_pending_lifecycle_request()
        for rec in self:
            if rec.state != "rfq" or not rec.rfq_review_required:
                raise UserError(_("This requisition is not waiting for post-reset RFQ review."))
            cfg = rec._get_approval_config()
            if (
                not rec._user_in_users(cfg.link_user_ids)
                and not self.env.user.has_group("base.group_system")
            ):
                raise UserError(_("Only configured RFQ Create users can complete the RFQ review."))
            if not rec.rfq_created:
                raise UserError(_("No active RFQ/PO is linked. Create or link an RFQ first."))

            summary = _("Review linked RFQ(s) after reset for %s") % rec.name
            rec._close_stage_activities(
                summary=summary,
                feedback=_("Linked RFQ(s) reviewed after reset by: %s") % self.env.user.display_name,
                strict_assigned=False,
            )
            rec.write({"rfq_review_required": False})
            rec.message_post(body=Markup(_(
                "<b>RFQ review completed after PR reset</b><br/>Reviewed by: %s<br/>Sent for Approval."
            )) % self.env.user.display_name)
            rec._approve_scm_activities()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_mark_rfq_issued(self):
        self._check_no_pending_lifecycle_request()
        return super().action_mark_rfq_issued()

    def _recompute_procurement_state(self):
        """Update PR completion from linked PO document state only; no line/quantity reconciliation."""
        for rec in self:
            rec.invalidate_recordset(["purchase_order_ids", "active_purchase_order_ids", "rfq_count", "rfq_created"])
            if rec.state == "canceled":
                continue
            has_confirmed_po = bool(rec.purchase_order_ids.filtered(lambda po: po.state in CONFIRMED_PO_STATES))
            if has_confirmed_po and rec.state == "po_issued":
                rec._close_stage_activities(
                    summary=_("Create Purchase Order for %s") % rec.name,
                    feedback=_("A linked Purchase Order was confirmed."),
                    strict_assigned=False,
                )
                rec.with_context(skip_pr_lifecycle_checks=True).state = "done"
                rec.message_post(body=_("A linked Purchase Order was confirmed. PR marked Done."))
            elif not has_confirmed_po and rec.state == "done":
                rec.with_context(skip_pr_lifecycle_checks=True).state = "po_issued"
                rec.message_post(body=_("No linked confirmed Purchase Order remains. PR returned to Issue PO stage."))

    def action_create_rfq(self):
        self._check_no_pending_lifecycle_request()
        return super().action_create_rfq()

    def action_create_po_from_supply(self):
        self._check_no_pending_lifecycle_request()
        return super().action_create_po_from_supply()
