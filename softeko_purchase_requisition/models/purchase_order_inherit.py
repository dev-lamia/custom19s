# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


RFQ_STATES = ("draft", "sent", "to approve")
CONFIRMED_PO_STATES = ("purchase",)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    pr_requisition_id = fields.Many2one(
        "softeko.purchase.requisition",
        string="Purchase Requisition",
        help="Legacy single Purchase Requisition link. Kept for compatibility.",
        copy=False,
        index=True,
    )
    pr_requisition_ids = fields.Many2many(
        "softeko.purchase.requisition",
        "softeko_purchase_requisition_purchase_order_rel",
        "purchase_order_id",
        "requisition_id",
        string="Purchase Requisitions",
        help="Document-level link between this RFQ/PO and one or more Purchase Requisitions.",
        copy=False,
    )

    pr_requisition_count = fields.Integer(
        string="Purchase Requisition Count",
        compute="_compute_pr_requisition_count",
    )

    def _compute_pr_requisition_count(self):
        for order in self:
            order.pr_requisition_count = len(order._get_linked_requisitions())

    def _get_approval_config(self, company=None):
        if not company and len(self) == 1 and self.company_id:
            company = self.company_id
        return self.env["softeko.purchase.requisition.approval"].sudo().get_company_config(company or self.env.company)

    def _can_link_requisition(self, requisitions=None, company=None):
        if self.env.user.has_group("base.group_system"):
            return True
        companies = requisitions.mapped("company_id") if requisitions else self.env["res.company"]
        if not companies and company:
            companies = company
        if not companies and len(self) == 1 and self.company_id:
            companies = self.company_id
        if not companies:
            companies = self.env.company
        for target_company in companies:
            cfg = self._get_approval_config(target_company)
            allowed = (cfg.link_user_ids | cfg.po_user_ids).filtered(lambda u: not u.share)
            if self.env.user not in allowed:
                return False
        return True

    def _get_requisition_ids_from_commands(self, commands):
        ids = set()
        if not commands:
            return ids
        for command in commands:
            if isinstance(command, int):
                ids.add(command)
                continue
            if not isinstance(command, (list, tuple)) or not command:
                continue
            operation = command[0]
            if operation == 6 and len(command) > 2:
                ids.update(command[2] or [])
            elif operation == 4 and len(command) > 1:
                ids.add(command[1])
            elif operation == 5:
                ids.clear()
        return ids

    def _get_linked_requisitions(self):
        self.ensure_one()
        requisitions = self.env["softeko.purchase.requisition"]
        if self.pr_requisition_id:
            requisitions |= self.pr_requisition_id
        requisitions |= self.pr_requisition_ids
        return requisitions

    def _get_all_pr_requisitions(self):
        """Return document-level PR links only; line-level traceability is intentionally not used."""
        self.ensure_one()
        return self._get_linked_requisitions()

    def _sync_pr_alternative_group_links(self):
        """Keep only document-level PR links consistent across Alternative RFQs."""
        for order in self.filtered("purchase_group_id"):
            other_orders = order.purchase_group_id.order_ids - order
            other_prs = self.env["softeko.purchase.requisition"]
            for other in other_orders:
                other_prs |= other._get_linked_requisitions()
            if not other_prs:
                continue

            own_prs = order._get_linked_requisitions()
            if own_prs and set(own_prs.ids) != set(other_prs.ids):
                raise UserError(_(
                    "This RFQ cannot be linked as an Alternative because its Purchase Requisition links "
                    "do not match the other RFQs in the Alternative group."
                ))

            if not own_prs:
                order.with_context(skip_pr_requisition_sync=True).write({
                    "pr_requisition_id": other_prs[:1].id,
                    "pr_requisition_ids": [(6, 0, other_prs.ids)],
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            requisition_ids = set()
            if vals.get("pr_requisition_id"):
                requisition_ids.add(vals["pr_requisition_id"])
            requisition_ids.update(self._get_requisition_ids_from_commands(vals.get("pr_requisition_ids")))
            requisitions = self.env["softeko.purchase.requisition"].sudo().browse(list(requisition_ids))
            if requisitions:
                companies = requisitions.mapped("company_id")
                if len(companies) > 1:
                    raise UserError(_("You cannot link Purchase Requisitions from multiple companies on one RFQ/PO."))
                vals["company_id"] = companies.id
                if not self._can_link_requisition(requisitions=requisitions):
                    raise UserError(_("You are not allowed to link a Purchase Requisition on an RFQ/PO for this company."))
                if not vals.get("pr_requisition_id"):
                    vals["pr_requisition_id"] = requisitions[:1].id
                vals["pr_requisition_ids"] = [(6, 0, requisitions.ids)]

        orders = super().create(vals_list)
        orders._sync_pr_alternative_group_links()
        orders._notify_scm_if_pr_ready()
        orders._check_pending_pr_requests()
        return orders

    def write(self, vals):
        if self.env.context.get("skip_pr_requisition_sync"):
            return super().write(vals)

        before_prs = self.mapped("pr_requisition_id") | self.mapped("pr_requisition_ids")
        link_fields_changed = "pr_requisition_id" in vals or "pr_requisition_ids" in vals

        if link_fields_changed:
            non_rfq = self.filtered(lambda order: order.state not in RFQ_STATES)
            if non_rfq:
                raise UserError(_(
                    "Purchase Requisition links can only be changed while the purchase document is an unconfirmed RFQ. "
                    "Confirmed, done, or cancelled Purchase Orders cannot be newly linked or unlinked."
                ))
            incoming_ids = set()
            if vals.get("pr_requisition_id"):
                incoming_ids.add(vals["pr_requisition_id"])
            incoming_ids.update(self._get_requisition_ids_from_commands(vals.get("pr_requisition_ids")))
            incoming = self.env["softeko.purchase.requisition"].sudo().browse(list(incoming_ids))
            for order in self:
                requisitions = order._get_linked_requisitions().sudo() | incoming
                companies = requisitions.mapped("company_id")
                if len(companies) > 1:
                    raise UserError(_("You cannot link Purchase Requisitions from multiple companies on one RFQ/PO."))
                if companies and order.company_id and order.company_id != companies:
                    raise UserError(_("The RFQ/PO company must match the Purchase Requisition company."))
                if requisitions and not order._can_link_requisition(requisitions=requisitions, company=order.company_id):
                    raise UserError(_("You are not allowed to link/unlink Purchase Requisitions on this RFQ/PO."))

        res = super().write(vals)

        if "purchase_group_id" in vals:
            self._sync_pr_alternative_group_links()

        if link_fields_changed:
            for order in self:
                requisitions = order.pr_requisition_ids | order.pr_requisition_id
                sync_vals = {}
                if order.pr_requisition_id and order.pr_requisition_id not in order.pr_requisition_ids:
                    sync_vals["pr_requisition_ids"] = [(6, 0, requisitions.ids)]
                if "pr_requisition_ids" in vals:
                    sync_vals["pr_requisition_id"] = order.pr_requisition_ids[:1].id if order.pr_requisition_ids else False
                if sync_vals:
                    order.with_context(skip_pr_requisition_sync=True).write(sync_vals)
            self._notify_scm_if_pr_ready()

        after_prs = self.mapped("pr_requisition_id") | self.mapped("pr_requisition_ids")
        affected = (before_prs | after_prs).sudo()
        if affected:
            affected._recompute_procurement_state()
            affected._check_cancel_dependencies()
        self._check_pending_pr_requests()
        return res

    def _validate_pr_confirmation_stage(self):
        """Keep workflow-stage controls, but perform no line mapping or quantity validation."""
        for order in self.filtered(lambda po: po.state in RFQ_STATES):
            requisitions = order._get_linked_requisitions()
            if not requisitions:
                continue

            invalid_stage = requisitions.filtered(lambda pr: pr.state != "po_issued")
            if invalid_stage:
                raise UserError(_(
                    "This RFQ/PO cannot be confirmed yet. The following Purchase Requisition(s) "
                    "must be in Issue PO stage: %s"
                ) % ", ".join(invalid_stage.mapped("name")))

            pending = requisitions.filtered(lambda pr: pr.reset_requested or pr.cancel_requested)
            if pending:
                raise UserError(_(
                    "This RFQ/PO cannot be confirmed while a PR reset/cancellation request is pending: %s"
                ) % ", ".join(pending.mapped("name")))

    def button_confirm(self):
        self._validate_pr_confirmation_stage()
        res = super().button_confirm()
        if not isinstance(res, dict):
            linked = self.mapped("pr_requisition_ids") | self.mapped("pr_requisition_id")
            linked._recompute_procurement_state()
        return res

    def button_approve(self, force=False):
        self._validate_pr_confirmation_stage()
        res = super().button_approve(force=force)
        linked = self.mapped("pr_requisition_ids") | self.mapped("pr_requisition_id")
        linked._recompute_procurement_state()
        return res

    def button_cancel(self):
        linked = self.mapped("pr_requisition_ids") | self.mapped("pr_requisition_id")
        res = super().button_cancel()
        linked._recompute_procurement_state()
        linked._check_cancel_dependencies()
        self._check_pending_pr_requests()
        return res

    def button_draft(self):
        linked = self.mapped("pr_requisition_ids") | self.mapped("pr_requisition_id")
        res = super().button_draft()
        linked._recompute_procurement_state()
        self._check_pending_pr_requests()
        return res

    def _notify_scm_if_pr_ready(self):
        for order in self:
            for pr in order._get_linked_requisitions():
                if pr.state != "rfq":
                    continue

                if pr.rfq_review_required:
                    pr._create_rfq_recheck_activities()
                    continue

                pr._close_stage_activities(
                    summary=_("Create RFQ/PO & Link %s") % pr.name,
                    feedback=_("RFQ/PO linked by: %s") % self.env.user.name,
                    strict_assigned=False,
                )
                pr._approve_scm_activities()

    def _check_pending_pr_requests(self):
        requisitions = self.mapped("pr_requisition_ids") | self.mapped("pr_requisition_id")
        if requisitions:
            requisitions.sudo()._check_reset_dependencies()
            requisitions.sudo()._check_cancel_dependencies()

    
    def action_view_pr_requisitions(self):
        self.ensure_one()

        requisitions = self._get_linked_requisitions()

        if not requisitions:
            return False

        # One PR: open directly
        if len(requisitions) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Purchase Requisition"),
                "res_model": "softeko.purchase.requisition",
                "view_mode": "form",
                "res_id": requisitions.id,
                "target": "current",
            }

        # Multiple PRs: show list, then user can open whichever PR they need
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Requisitions"),
            "res_model": "softeko.purchase.requisition",
            "view_mode": "list,form",
            "domain": [("id", "in", requisitions.ids)],
            "target": "current",
        }
