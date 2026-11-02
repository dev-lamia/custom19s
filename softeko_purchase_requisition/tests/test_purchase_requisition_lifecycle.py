# -*- coding: utf-8 -*-
"""Current workflow regression tests for Purchase Requisition.

The suite intentionally follows the three supported business flows:

* normal Purchase Requisition (no Sale Order),
* Purchase Requisition linked to a Sale Order,
* Office Supply Purchase Requisition.

It focuses on stage ownership, Reset to Draft, linked RFQ/PO dependencies,
resubmission after reset, and cancellation.  Older tests that asserted removed
line-traceability or obsolete notification implementation details are not kept.
"""

from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pr_current_workflow")
class TestPurchaseRequisitionCurrentWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.vendor = cls.env["res.partner"].sudo().create({
            "name": "PR Workflow Vendor",
            "supplier_rank": 1,
        })
        cls.customer = cls.env["res.partner"].sudo().create({
            "name": "PR Workflow Customer",
            "customer_rank": 1,
        })
        cls.product = cls.env["product.product"].sudo().create({
            "name": "PR Workflow Product",
            "purchase_ok": True,
            "sale_ok": True,
            "standard_price": 10.0,
            "list_price": 25.0,
        })

        cls.requester = cls._create_user(
            "PR Requester", "pr_test_requester", scope="own",
            extra_groups=("sales_team.group_sale_salesman",),
        )
        cls.manager = cls._create_user(
            "PR Manager", "pr_test_manager", scope="team",
        )
        cls.rfq_user = cls._create_user(
            "PR RFQ Create", "pr_test_rfq", scope="team",
            extra_groups=("purchase.group_purchase_user",),
        )
        cls.scm_user = cls._create_user(
            "PR SCM Approver", "pr_test_scm", scope="team",
        )
        cls.finance_user = cls._create_user(
            "PR Finance Approver", "pr_test_finance", scope="team",
        )
        cls.po_user = cls._create_user(
            "PR PO Issuer", "pr_test_po", scope="team",
            # Keep PR tests independent from the database's Purchase double-
            # validation threshold.  The configured PO Issuer can therefore
            # confirm the test PO all the way to `purchase` in one action.
            extra_groups=("purchase.group_purchase_manager",),
        )
        # Admin scope gives this user record-rule visibility while keeping them
        # outside every lifecycle role.  That lets us test method-level denial.
        cls.outsider = cls._create_user(
            "PR Outsider", "pr_test_outsider", scope="admin",
        )

        # Keep this PR suite isolated from unrelated HR customizations.
        # Several production addons override hr.employee.create(); if one of
        # them is broken, PR regression tests should not fail in setUpClass
        # before any PR workflow is exercised.  The PR model only needs the
        # requester's direct manager relationship for these tests, so provide
        # that relationship in-memory while all PR/RFQ/PO/user records remain
        # real ORM records with their real access checks.
        manager_stub = SimpleNamespace(user_id=cls.manager, parent_id=False)
        requester_stub = SimpleNamespace(
            user_id=cls.requester,
            parent_id=manager_stub,
            company_id=cls.company,
            department_id=False,
            id=False,
        )

        model_class = type(cls.env["softeko.purchase.requisition"])

        def _test_get_employee_for_user(recordset, user=None, company=None):
            user = user or recordset.env.user
            if user.id == cls.requester.id:
                return requester_stub
            return False

        cls._employee_lookup_patch = patch.object(
            model_class,
            "_get_employee_for_user",
            _test_get_employee_for_user,
        )
        cls._employee_lookup_patch.start()
        cls.addClassCleanup(cls._employee_lookup_patch.stop)

        Config = cls.env["softeko.purchase.requisition.approval"].sudo()
        cls.config = Config.search([("company_id", "=", cls.company.id)], limit=1)
        if not cls.config:
            cls.config = Config.create({
                "name": "Workflow Test Approval Configuration",
                "company_id": cls.company.id,
            })
        cls.config.write({
            "link_user_ids": [Command.set(cls.rfq_user.ids)],
            "scm_approver_ids": [Command.set(cls.scm_user.ids)],
            "finance_user_ids": [Command.set(cls.finance_user.ids)],
            "po_user_ids": [Command.set(cls.po_user.ids)],
            "no_manager_approval_employee_ids": [Command.clear()],
        })

    @classmethod
    def _create_user(cls, name, login, *, scope="team", extra_groups=()):
        group_ids = [cls.env.ref("base.group_user").id]
        for xmlid in extra_groups:
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        return cls.env["res.users"].with_context(no_reset_password=True).sudo().create({
            "name": name,
            "login": login,
            "email": "%s@example.com" % login,
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "pr_access_scope": scope,
            "group_ids": [Command.set(group_ids)],
        })

    # ------------------------------------------------------------------
    # Fixtures / stage helpers
    # ------------------------------------------------------------------

    def _make_sale_order(self):
        return self.env["sale.order"].sudo().create({
            "partner_id": self.customer.id,
            "company_id": self.company.id,
            "user_id": self.requester.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "product_uom_id": self.product.uom_id.id,
                "price_unit": 25.0,
            })],
        })

    def _make_pr(self, *, flow="normal", requester=None, sale_order=None):
        requester = requester or self.requester
        vals = {
            "requester_id": requester.id,
            "company_id": self.company.id,
            # Explicit False values prevent the model defaults from looking up
            # a persisted hr.employee; manager resolution is intentionally
            # provided by the isolated in-memory relationship above.
            "employee_id": False,
            "department_id": False,
            "from_office_supply": flow == "office_supply",
            "material_line_ids": [Command.create({
                "product_id": self.product.id,
                "product_qty": 2.0,
                "product_uom_id": self.product.uom_id.id,
                "estimated_price": 20.0,
            })],
        }
        if sale_order:
            vals["sale_order_id"] = sale_order.id
        return self.env["softeko.purchase.requisition"].sudo().create(vals)

    def _make_linked_rfq(self, pr, *, user=None):
        user = user or self.rfq_user
        return self.env["purchase.order"].with_user(user).create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "pr_requisition_id": pr.id,
            "pr_requisition_ids": [Command.set(pr.ids)],
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_qty": 2.0,
                "product_uom_id": self.product.uom_id.id,
                "price_unit": 10.0,
                "date_planned": fields.Datetime.now(),
            })],
        })

    def _submit(self, pr):
        pr.with_user(pr.requester_id).action_submit()
        self.assertEqual(pr.state, "finance_approved" if pr.from_office_supply else "submitted")
        return pr

    def _manager_approve(self, pr):
        pr.with_user(self.manager).action_manager_approve()
        self.assertEqual(pr.state, "rfq")
        return pr

    def _link_rfq(self, pr):
        rfq = self._make_linked_rfq(pr, user=self.rfq_user)
        pr.invalidate_recordset(["rfq_created", "rfq_count", "purchase_order_ids"])
        self.assertTrue(pr.rfq_created)
        self.assertIn(rfq, pr.purchase_order_ids)
        return rfq

    def _scm_approve(self, pr):
        pr.with_user(self.scm_user).action_mark_rfq_issued()
        self.assertEqual(pr.state, "finance_approved")
        return pr

    def _finance_approve(self, pr):
        pr.with_user(self.finance_user).action_fd_approve()
        expected = "sale_order" if pr.sale_order_id and pr.sale_order_id.state not in ("sale", "done") else "po_issued"
        self.assertEqual(pr.state, expected)
        return pr

    def _reach_normal_stage(self, stage, *, with_sale_order=False):
        sale = self._make_sale_order() if with_sale_order else None
        pr = self._make_pr(flow="sale_order" if with_sale_order else "normal", sale_order=sale)
        self._submit(pr)
        if stage == "submitted":
            return pr, False, sale
        self._manager_approve(pr)
        if stage == "rfq_unlinked":
            return pr, False, sale
        rfq = self._link_rfq(pr)
        if stage == "rfq_linked":
            return pr, rfq, sale
        self._scm_approve(pr)
        if stage == "finance_approved":
            return pr, rfq, sale
        self._finance_approve(pr)
        if with_sale_order:
            if stage == "sale_order":
                return pr, rfq, sale
            sale.with_user(self.requester).action_confirm()
            pr.invalidate_recordset(["state"])
            self.assertEqual(pr.state, "po_issued")
        if stage == "po_issued":
            return pr, rfq, sale
        if stage == "done":
            rfq.with_user(self.po_user).button_confirm()
            pr.invalidate_recordset(["state"])
            self.assertEqual(pr.state, "done")
            return pr, rfq, sale
        raise AssertionError("Unsupported stage fixture: %s" % stage)

    def _reach_office_supply_stage(self, stage):
        pr = self._make_pr(flow="office_supply")
        self._submit(pr)
        if stage == "finance_approved":
            return pr, False
        self._finance_approve(pr)
        if stage == "po_issued":
            return pr, False
        if stage == "done":
            po = self._make_linked_rfq(pr, user=self.po_user)
            po.with_user(self.po_user).button_confirm()
            pr.invalidate_recordset(["state"])
            self.assertEqual(pr.state, "done")
            return pr, po
        raise AssertionError("Unsupported Office Supply stage fixture: %s" % stage)

    def _assert_reset_to_draft(self, pr, actor, *, review_required=False, reason="Workflow regression reset"):
        pr.with_user(actor).action_request_reset(reason)
        pr.invalidate_recordset(["state", "rfq_review_required", "reset_requested"])
        self.assertEqual(pr.state, "draft")
        self.assertFalse(pr.reset_requested)
        self.assertEqual(pr.rfq_review_required, review_required)

    # ------------------------------------------------------------------
    # Three supported end-to-end flows
    # ------------------------------------------------------------------

    def test_flow_normal_without_sale_order_to_done(self):
        pr, rfq, _sale = self._reach_normal_stage("done")
        self.assertEqual(pr.state, "done")
        self.assertEqual(rfq.state, "purchase")

    def test_flow_with_sale_order_to_done(self):
        pr, rfq, sale = self._reach_normal_stage("done", with_sale_order=True)
        self.assertEqual(sale.state, "sale")
        self.assertEqual(pr.state, "done")
        self.assertEqual(rfq.state, "purchase")

    def test_flow_office_supply_bypasses_manager_and_scm_and_reaches_done(self):
        pr = self._make_pr(flow="office_supply")
        self.assertFalse(self.requester.has_group("purchase.group_purchase_user"))
        self.assertFalse(self.requester.has_group("account.group_account_user"))

        pr.with_user(self.requester).action_submit()
        self.assertEqual(pr.state, "finance_approved")
        self.assertFalse(pr.rfq_created)

        pr.with_user(self.finance_user).action_fd_approve()
        self.assertEqual(pr.state, "po_issued")

        po = self._make_linked_rfq(pr, user=self.po_user)
        po.with_user(self.po_user).button_confirm()
        pr.invalidate_recordset(["state"])
        self.assertEqual(pr.state, "done")

    # ------------------------------------------------------------------
    # Reset to Draft: stage + responsible user matrix
    # ------------------------------------------------------------------

    def test_reset_submitted_stage_by_requester(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        self._assert_reset_to_draft(pr, self.requester)

    def test_reset_submitted_stage_by_manager(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        self._assert_reset_to_draft(pr, self.manager)

    def test_reset_rfq_link_stage_by_rfq_create_user(self):
        pr, _rfq, _sale = self._reach_normal_stage("rfq_unlinked")
        self._assert_reset_to_draft(pr, self.rfq_user, review_required=False)

    def test_reset_rfq_approval_stage_by_scm_approver_keeps_rfq_for_review(self):
        pr, rfq, _sale = self._reach_normal_stage("rfq_linked")
        self._assert_reset_to_draft(pr, self.scm_user, review_required=True)
        self.assertIn(rfq, pr.purchase_order_ids)
        self.assertEqual(rfq.state, "draft")

    def test_reset_finance_stage_by_finance_approver_keeps_rfq_for_review(self):
        pr, rfq, _sale = self._reach_normal_stage("finance_approved")
        self._assert_reset_to_draft(pr, self.finance_user, review_required=True)
        self.assertIn(rfq, pr.purchase_order_ids)

    def test_reset_issue_po_stage_by_po_issuer_keeps_rfq_for_review(self):
        pr, rfq, _sale = self._reach_normal_stage("po_issued")
        self._assert_reset_to_draft(pr, self.po_user, review_required=True)
        self.assertIn(rfq, pr.purchase_order_ids)

    def test_reset_confirmed_po_waits_for_po_to_return_to_draft_then_finalizes(self):
        pr, po, _sale = self._reach_normal_stage("done")

        pr.with_user(self.requester).action_request_reset("Amend after PO confirmation")
        pr.invalidate_recordset(["reset_requested", "state"])
        self.assertTrue(pr.reset_requested)
        self.assertEqual(pr.state, "done")
        self.assertIn(po, pr.reset_blocking_po_ids)

        po.with_user(self.po_user).button_cancel()
        po.with_user(self.po_user).button_draft()
        self.assertEqual(po.state, "draft")

        pr.with_user(self.requester).action_finalize_reset()
        pr.invalidate_recordset(["state", "reset_requested", "rfq_review_required"])
        self.assertEqual(pr.state, "draft")
        self.assertFalse(pr.reset_requested)
        self.assertTrue(pr.rfq_review_required)
        self.assertIn(po, pr.purchase_order_ids)

    def test_reset_with_existing_rfq_resubmit_requires_rfq_review_before_scm(self):
        pr, rfq, _sale = self._reach_normal_stage("finance_approved")
        self._assert_reset_to_draft(pr, self.finance_user, review_required=True)

        pr.with_user(self.requester).action_submit()
        self.assertEqual(pr.state, "submitted")
        pr.with_user(self.manager).action_manager_approve()
        self.assertEqual(pr.state, "rfq")
        self.assertTrue(pr.rfq_review_required)

        review_summary = "Review linked RFQ(s) after reset for %s" % pr.name
        self.assertTrue(pr.activity_ids.sudo().filtered(
            lambda a: a.user_id == self.rfq_user and a.summary == review_summary
        ))

        pr.with_user(self.rfq_user).action_complete_rfq_review()
        self.assertFalse(pr.rfq_review_required)
        self.assertIn(rfq, pr.purchase_order_ids)

        pr.with_user(self.scm_user).action_mark_rfq_issued()
        self.assertEqual(pr.state, "finance_approved")

    def test_sale_order_stage_reset_and_resubmit_returns_to_sale_order_flow(self):
        pr, rfq, sale = self._reach_normal_stage("sale_order", with_sale_order=True)
        self._assert_reset_to_draft(pr, self.requester, review_required=True)

        pr.with_user(self.requester).action_submit()
        pr.with_user(self.manager).action_manager_approve()
        pr.with_user(self.rfq_user).action_complete_rfq_review()
        pr.with_user(self.scm_user).action_mark_rfq_issued()
        pr.with_user(self.finance_user).action_fd_approve()

        self.assertEqual(pr.state, "sale_order")
        self.assertIn(rfq, pr.purchase_order_ids)
        self.assertEqual(sale.state, "draft")

    def test_office_supply_requester_without_purchase_access_can_reset_finance_and_resubmit(self):
        pr, _po = self._reach_office_supply_stage("finance_approved")
        self.assertFalse(self.requester.has_group("purchase.group_purchase_user"))
        self.assertFalse(self.requester.has_group("account.group_account_user"))

        self._assert_reset_to_draft(pr, self.requester, review_required=False)
        pr.material_line_ids.sudo().write({"estimated_price": 35.0})
        pr.with_user(self.requester).action_submit()
        self.assertEqual(pr.state, "finance_approved")

    def test_office_supply_finance_user_can_reset_finance(self):
        pr, _po = self._reach_office_supply_stage("finance_approved")
        self._assert_reset_to_draft(pr, self.finance_user, review_required=False)

    def test_office_supply_requester_can_reset_issue_po_before_po_exists(self):
        pr, _po = self._reach_office_supply_stage("po_issued")
        self._assert_reset_to_draft(pr, self.requester, review_required=False)

    def test_office_supply_send_back_is_blocked(self):
        pr, _po = self._reach_office_supply_stage("finance_approved")
        with self.assertRaisesRegex(UserError, "Send Back is not used for Office Supply"):
            pr.with_user(self.finance_user).action_fd_review()
        self.assertEqual(pr.state, "finance_approved")

    def test_non_stakeholder_cannot_reset_or_cancel(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        with self.assertRaises(UserError):
            pr.with_user(self.outsider).action_request_reset("Not my PR")
        with self.assertRaises(UserError):
            pr.with_user(self.outsider).action_request_cancel("Not my PR")

    def test_manual_todo_survives_reset_while_workflow_activities_are_closed(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        todo_type = self.env.ref("mail.mail_activity_data_todo")
        manual = pr.sudo().activity_schedule(
            activity_type_id=todo_type.id,
            user_id=self.requester.id,
            summary="Manual follow-up that must survive reset",
        )

        pr.with_user(self.requester).action_request_reset("Check manual activity cleanup")

        self.assertTrue(manual.exists())
        self.assertEqual(manual.summary, "Manual follow-up that must survive reset")
        workflow_type = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        stale_workflow = pr.activity_ids.sudo().filtered(
            lambda a: a.activity_type_id == workflow_type
            and a.summary != "Requisition Review"
        )
        self.assertFalse(stale_workflow)

    # ------------------------------------------------------------------
    # Cancellation: no dependency, RFQ dependency, confirmed PO dependency
    # ------------------------------------------------------------------

    def test_cancel_without_linked_rfq_is_immediate(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        pr.with_user(self.requester).action_request_cancel("No longer required")
        pr.invalidate_recordset(["state", "cancel_requested"])
        self.assertEqual(pr.state, "canceled")
        self.assertFalse(pr.cancel_requested)

    def test_cancel_with_draft_rfq_waits_until_rfq_is_cancelled(self):
        pr, rfq, _sale = self._reach_normal_stage("rfq_linked")
        pr.with_user(self.requester).action_request_cancel("Stop procurement")
        pr.invalidate_recordset(["state", "cancel_requested"])
        self.assertEqual(pr.state, "rfq")
        self.assertTrue(pr.cancel_requested)

        rfq.with_user(self.rfq_user).button_cancel()
        pr.invalidate_recordset(["state", "cancel_requested"])
        self.assertEqual(pr.state, "canceled")
        self.assertFalse(pr.cancel_requested)

    def test_cancel_with_confirmed_po_waits_until_po_is_cancelled(self):
        pr, po, _sale = self._reach_normal_stage("done")
        pr.with_user(self.requester).action_request_cancel("Cancel after PO confirmation")
        pr.invalidate_recordset(["cancel_requested"])
        self.assertTrue(pr.cancel_requested)
        self.assertIn(po, pr.cancel_blocking_po_ids)

        po.with_user(self.po_user).button_cancel()
        pr.invalidate_recordset(["state", "cancel_requested"])
        self.assertEqual(pr.state, "canceled")
        self.assertFalse(pr.cancel_requested)

    def test_sale_order_flow_cancel_waits_for_linked_rfq(self):
        pr, rfq, sale = self._reach_normal_stage("sale_order", with_sale_order=True)
        pr.with_user(self.requester).action_request_cancel("Cancel sale-linked procurement")
        self.assertTrue(pr.cancel_requested)

        rfq.with_user(self.rfq_user).button_cancel()
        pr.invalidate_recordset(["state", "cancel_requested"])
        self.assertEqual(pr.state, "canceled")
        self.assertFalse(pr.cancel_requested)
        self.assertEqual(sale.state, "draft")

    def test_normal_cancelled_pr_can_be_reset_to_draft(self):
        pr, _rfq, _sale = self._reach_normal_stage("submitted")
        pr.with_user(self.requester).action_request_cancel("Temporary cancellation")
        self.assertEqual(pr.state, "canceled")

        pr.with_user(self.requester).action_request_reset("Reopen procurement")
        self.assertEqual(pr.state, "draft")

    def test_office_supply_cancel_is_final_and_cannot_be_reset(self):
        pr, _po = self._reach_office_supply_stage("finance_approved")
        pr.with_user(self.requester).action_request_cancel("Office Supply no longer required")
        self.assertEqual(pr.state, "canceled")

        with self.assertRaisesRegex(UserError, "cancelled Office Supply PR cannot be reopened"):
            pr.with_user(self.requester).action_request_reset("Try to reopen")
