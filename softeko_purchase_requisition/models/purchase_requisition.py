# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models, _, modules
from odoo.fields import Domain
from odoo.exceptions import UserError


class PurchaseRequisition(models.Model):
    _name = "softeko.purchase.requisition"
    _description = "Purchase Requisition"
    _inherit = ["mail.thread", "mail.activity.mixin", "product.catalog.mixin"]
    _order = "id desc"

    # ---------- Defaults using sudo() so all employees can create ----------
    def _get_employee_for_user(self, user=None, company=None):
        """Return the user's employee without forcing the selected company.

        In multi-company, user.employee_id is company-dependent. If the user is
        working in PR Trading but his actual employee record is only in PR
        Gulf, employee_id becomes empty and manager approval breaks. Prefer the
        document/current company employee when it exists, otherwise fall back to
        any employee linked to the same user.
        """
        user = user or self.env.user
        company = company or self.env.company

        employees = user.sudo().employee_ids

        employee = employees.filtered(lambda emp: emp.company_id == company)[:1]
        if not employee:
            employee = employees.filtered(lambda emp: not emp.company_id)[:1]
        if not employee:
            employee = employees[:1]
        if not employee:
            employee = self.env["hr.employee"].sudo().search(
                [("user_id", "=", user.id)],
                limit=1,
            )

        return employee

    def _default_employee(self):
        return self._get_employee_for_user(self.env.user).id

    def _default_department(self):
        employee = self._get_employee_for_user(self.env.user)
        return employee.department_id.id if employee and employee.department_id else False

    # ---------- Fields ----------
    name = fields.Char(
        string="Requisition No.",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    requester_id = fields.Many2one(
        "res.users",
        string="Name",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )

    employee_id = fields.Many2one("hr.employee", string="Employee", default=_default_employee)
    department_id = fields.Many2one(
        "hr.department", string="Department", default=_default_department, tracking=True
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    date_request = fields.Date(
        string="Date", default=fields.Date.context_today, required=True, tracking=True
    )

    cost_center = fields.Char(string="Cost Center")
    project_ref = fields.Char(string="Project Reference")
    special_instruction = fields.Text(string="Special Instruction")

    # ✅ Sale Order linkage
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        tracking=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="sale_order_id.partner_id",
        store=True,
        readonly=True,
    )
    customer_credit_limit = fields.Float(
        string="Customer Credit Limit",
        related="customer_id.credit_limit",
        store=True,
        readonly=True,
    )
    sale_order_state = fields.Selection(
        related="sale_order_id.state",
        string="SO State",
        store=True,
        readonly=True,
    )

    sale_order_trigger = fields.Boolean(
        string="Sale Order Trigger",
        compute="_compute_sale_order_confirmation",
        store=False,
    )

    material_line_ids = fields.One2many(
        "softeko.purchase.requisition.line",
        "pr_requisition_id",
        string="Material Detail",
    )

    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="RFQs / Purchase Orders",
        compute="_compute_purchase_order_ids",
        readonly=True,
    )

    from_office_supply = fields.Boolean(
        string="From Office Supply",
        default=False,
        copy=False,
        tracking=True,
    )

    rfq_count = fields.Integer(string="RFQ Count", compute="_compute_rfq_info")
    rfq_created = fields.Boolean(string="RFQ Created", compute="_compute_rfq_info")
    manager_user_id = fields.Many2one(
        "res.users",
        string="Manager User",
        compute="_compute_manager_user_id",
        store=True,
        index=True,
    )


    @api.depends("requester_id", "company_id")
    def _compute_manager_user_id(self):
        for rec in self:
            rec.manager_user_id = False
            if not rec.requester_id:
                continue

            emp = rec._get_employee_for_user(rec.requester_id, rec.company_id)

            if emp and emp.parent_id and emp.parent_id.user_id:
                rec.manager_user_id = emp.parent_id.user_id.id

                
    def _get_purchase_order_domain(self):
        self.ensure_one()
        PO = self.env["purchase.order"]
        if "pr_requisition_ids" in PO._fields:
            return [
                ("state", "!=", "cancel"),
                "|",
                ("pr_requisition_id", "=", self.id),
                ("pr_requisition_ids", "in", self.id),
            ]
        return [("pr_requisition_id", "=", self.id), ("state", "!=", "cancel")]

    def _compute_purchase_order_ids(self):
        PO = self.env["purchase.order"].sudo()
        for rec in self:
            rec.purchase_order_ids = PO.search(rec._get_purchase_order_domain()) if rec.id else False

    @api.depends("purchase_order_ids")
    def _compute_rfq_info(self):
        """
        IMPORTANT:
        Don't rely on record rules for RFQ counters; purchase users and PR users can differ.
        Include both the legacy single-PR link and the new multi-PR link.
        """
        PO = self.env["purchase.order"].sudo()
        for rec in self:
            count = PO.search_count(rec._get_purchase_order_domain()) if rec.id else 0
            rec.rfq_count = count
            rec.rfq_created = count > 0

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted to Manager"),
            ("rfq", "SCM Approval"),
            ("finance_approved", "Finance Approval"),
            ("sale_order", "Confirm Sale Order"),
            ("po_issued", "Issue PO"),
            ("done", "Done"),
            ("canceled", "Canceled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        group_expand="_group_expand_state",
    )

    @api.model
    def _group_expand_state(self, states, domain, order=None):
        return [key for key, _label in self._fields["state"].selection]

    # -----------------------
    # Config-driven role helpers
    # -----------------------
    is_employee = fields.Boolean(string="Is Employee", compute="_compute_roles", store=False)
    is_manager = fields.Boolean(string="Is Manager", compute="_compute_roles", store=False)
    is_po_link = fields.Boolean(string="Is RFQ Create User", compute="_compute_roles", store=False)
    is_scm_approver = fields.Boolean(string="Is SCM Approver", compute="_compute_roles", store=False)
    is_finance = fields.Boolean(string="Is Finance", compute="_compute_roles", store=False)
    is_po_issuer = fields.Boolean(string="Is PO Issuer", compute="_compute_roles", store=False)

    def _get_approval_config(self, company=None):
        """Return approval config for the PR company, not the active UI company.

        In multi-company, users can work on a Hamria PR while their current
        company selector is Trading/Gulf. Approval users and activities must
        therefore be resolved from rec.company_id.
        """
        if not company and len(self) == 1 and self.company_id:
            company = self.company_id
        company = company or self.env.company
        return self.env["softeko.purchase.requisition.approval"].sudo().get_company_config(company)

    def _with_pr_company_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        allowed_company_ids = list(self.env.context.get("allowed_company_ids") or self.env.user.company_ids.ids)
        if company.id not in allowed_company_ids:
            allowed_company_ids.append(company.id)
        return self.with_company(company).with_context(
            allowed_company_ids=allowed_company_ids,
            company_id=company.id,
            force_company=company.id,
        )

    def _schedule_pr_activity(self, activity_type_id, user_id, summary, note=False):
        """Schedule PR activities under the requisition company.

        This keeps the activity visible when the assigned user selects the same
        company as the PR, instead of leaking the activity to whichever company
        the submitter had active in the company switcher.
        """
        self.ensure_one()
        activity = self._with_pr_company_context().sudo().activity_schedule(
            activity_type_id=activity_type_id,
            user_id=user_id,
            summary=summary,
            note=note,
        )
        if activity and self.company_id and "company_id" in activity._fields:
            activity.sudo().write({"company_id": self.company_id.id})
        return activity

    def _sync_company_from_sale_order(self):
        for rec in self:
            if rec.sale_order_id and rec.sale_order_id.company_id and rec.company_id != rec.sale_order_id.company_id:
                rec.with_context(skip_company_sync=True).write({"company_id": rec.sale_order_id.company_id.id})

    def _user_in_users(self, users):
        user = self.env.user
        return bool(users.filtered(lambda u: u.id == user.id and not u.share))

    @api.depends("requester_id", "company_id")
    @api.depends_context("uid")
    def _compute_roles(self):
        current_user = self.env.user

        for rec in self:
            cfg = rec._get_approval_config()
            rec.is_employee = rec.requester_id.id == current_user.id
            rec.is_manager = False

            if rec.requester_id and rec.requester_id.id != current_user.id:
                emp = rec._get_employee_for_user(rec.requester_id, rec.company_id)

                if emp and emp.parent_id and emp.parent_id.user_id:
                    rec.is_manager = emp.parent_id.user_id.id == current_user.id

            rec.is_po_link = rec._user_in_users(cfg.link_user_ids)
            rec.is_scm_approver = rec._user_in_users(cfg.scm_approver_ids)
            rec.is_finance = rec._user_in_users(cfg.finance_user_ids)
            rec.is_po_issuer = rec._user_in_users(cfg.po_user_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("softeko.purchase.requisition") or "New"
        return super().create(vals_list)

    # ---------------------------------------------------------
    # Sale Order -> bring sections, notes, product descriptions, category and UoM into PR lines
    # ---------------------------------------------------------
    @api.onchange("sale_order_id")
    def _onchange_sale_order_id_fill_lines(self):
        for rec in self:
            if not rec.sale_order_id:
                continue

            rec.company_id = rec.sale_order_id.company_id

            lines_cmd = [(5, 0, 0)]
            for sol in rec.sale_order_id.order_line.sorted("sequence"):
                vals = rec._prepare_requisition_line_from_sale_line(sol)
                if vals:
                    lines_cmd.append((0, 0, vals))
            rec.material_line_ids = lines_cmd

    def _prepare_requisition_line_from_sale_line(self, sol):
        vals = {
            "sequence": sol.sequence,
            "sale_line_id": sol.id,
            "display_type": sol.display_type,
            "name": sol.name,
        }
        if sol.display_type:
            vals.update({
                "product_qty": 0.0,
            })
            return vals

        if not sol.product_id:
            return False

        product = sol.product_id
        vals.update({
            "product_id": product.id,
            "categ_id": product.categ_id.id,
            "product_qty": sol.product_uom_qty,
            "product_uom_id": sol.product_uom_id.id,
        })
        return vals


    def action_update_sales_prices(self):
        """Update PR line Sales Price from linked RFQ/PO unit prices plus product margin."""
        updated_count = 0
        for rec in self:
            if not rec.purchase_order_ids:
                raise UserError(_("Please link at least one RFQ/PO before updating Sales Price."))

            product_lines = rec.material_line_ids.filtered(lambda line: not line.display_type and line.product_id)
            product_lines._update_sales_price_from_rfq_unit_prices()
            updated_count += len(product_lines)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Prices Updated"),
                "message": _("Updated Sales Price on %s requisition line(s).") % updated_count,
                "type": "success",
                "sticky": False,
                # Force the web client to fetch the updated one2many values.
                # Without this, the values are written in database but the line grid
                # stays stale until the user manually reloads the form.
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    # ---------- Common helpers ----------
    def _check_special_instruction_for_review(self):
        for rec in self:
            if not rec.special_instruction:
                raise UserError(_("Please fill in the Special Instruction field before sending back for review."))

    def _create_review_activity(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        for rec in self:
            if rec.requester_id:
                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=rec.requester_id.id,
                    summary=_("Requisition Review"),
                    note=_("Please review the purchase requisition %s.") % rec.name,
                )

    # Manager user resolver (more reliable for multi-company)
    def _get_requester_manager_user(self):
        self.ensure_one()
        if not self.requester_id:
            return False

        emp = self._get_employee_for_user(self.requester_id, self.company_id)

        if emp and emp.parent_id and emp.parent_id.user_id:
            return emp.parent_id.user_id

        return False

    def _requester_skips_manager_approval(self):
        """Whether this requester bypasses Manager Approval for this PR company.

        The exception is configured on the company-specific PR Approval record,
        not on hr.employee itself.  Match through employee.user_id so the rule
        also works when the user's HR employee record belongs to another company.
        """
        self.ensure_one()
        if not self.requester_id:
            return False
        cfg = self._get_approval_config()
        if not cfg:
            return False
        return self.requester_id in cfg.no_manager_approval_employee_ids.mapped("user_id")

    def _create_manager_approval_activity(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        for rec in self:
            manager_user = rec._get_requester_manager_user()
            if not manager_user:
                continue

            summary = _("Approve Purchase Requisition %s") % rec.name
            existing = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.user_id.id == manager_user.id
                and a.summary == summary
            )
            if existing:
                continue

            rec._schedule_pr_activity(
                activity_type_id=ActivityType.id,
                user_id=manager_user.id,
                summary=summary,
                note=_("A requisition (%s) was submitted and needs your approval.") % rec.name,
            )

    # RFQ Create activity (separate from SCM approval activity)
    def _create_po_link_activities(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            link_users = cfg.link_user_ids.filtered(lambda u: not u.share)
            for user in link_users:
                summary = _("Create RFQ/PO & Link %s") % rec.name
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=_(
                        "%(name)s is in RFQ/PO Link stage.\n"
                        "Please create an RFQ/PO and link this PR on the PO"
                    ) % {"name": rec.name},
                )

    def _approve_scm_activities(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            scm_users = cfg.scm_approver_ids.filtered(lambda u: not u.share)
            for user in scm_users:
                summary = _("%s ready for SCM approval") % rec.name
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=_("RFQ/PO has been created/linked for %s. Please open PR and approve.") % rec.name,
                )

    def _create_finance_activities(self):
        """Create finance approval activities."""
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            finance_users = cfg.finance_user_ids.filtered(lambda u: not u.share)
            summary = _("PR ready for Finance approval")

            if rec.from_office_supply:
                note_msg = _("Office Supply shortage created %s. Please open PR and approve.") % rec.name
            else:
                note_msg = _("RFQ/PO has been created/linked for %s. Please open PR and approve.") % rec.name

            for user in finance_users:
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=note_msg,
                )

    def _check_sale_order_confirmation(self):
        """
        Move PR to 'po_issued' if linked sale order is confirmed
        and create the correct PO activity for this path.
        """
        for rec in self:
            # Read the source document state directly.  The stored related
            # sale_order_state can still be stale inside the same transaction in
            # which sale.order.action_confirm() calls back into the PR.
            if rec.sale_order_id and rec.sale_order_id.state in ("sale", "done"):
                activities = rec.activity_ids.sudo().filtered(
                    lambda a: "Confirm Sale Order" in (a.summary or "")
                )
                for activity in activities:
                    activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Sale Order Confirmed"))

                rec.write({"state": "po_issued"})
                rec._create_po_creation_after_so_activity()

    def _create_so_creation_activity(self):
        """
        When Finance approves:
        -> create activity for Sale Order confirmation for the PR requester.
        Uses the Name field of the PR as reference in the activity.
        """
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            if not rec.requester_id:
                continue

            pr_name = rec.name
            summary = _("Confirm Sale Order for %s") % pr_name

            existing = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.user_id.id == rec.requester_id.id
                and a.summary == summary
            )
            if existing:
                continue

            rec._schedule_pr_activity(
                activity_type_id=ActivityType.id,
                user_id=rec.requester_id.id,
                summary=summary,
                note=_(
                    "Finance approved %s.\n"
                    "Please confirm the related Sale Order."
                ) % pr_name,
            )

    def _create_po_creation_activity(self):
        """
        When Finance approves:
        -> create activity for PO Issuer users (cfg.po_user_ids)
        """
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            po_users = cfg.po_user_ids.filtered(lambda u: not u.share)
            summary = _("Create Purchase Order for %s") % rec.name

            if rec.from_office_supply:
                note_msg = _(
                    "Finance approved %s.\n"
                    "This requisition came from Office Supply shortage.\n"
                    "Please create/confrirm Purchase Order."
                ) % rec.name
            else:
                note_msg = _(
                    "Finance approved %s.\n"
                    "Please create/confirm the Purchase Order from RFQ and ensure this PR is linked on the PO."
                ) % rec.name

            for user in po_users:
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=note_msg,
                )

    # ---------- Employee Actions ----------
    def action_submit(self):
        for rec in self:
            if rec.requester_id != self.env.user:
                raise UserError(_("Only the requester can submit this requisition."))
            if rec.state != "draft":
                raise UserError(_("Only requisitions in 'Draft' stage can be submitted."))
            if not rec.material_line_ids.filtered(lambda line: not line.display_type):
                raise UserError(_("Please add at least one product line before submitting."))

            rec._sync_company_from_sale_order()
            rec._validate_requester_manager_exists()
            rec._close_review_activity_for_requester()
            rec.state = "submitted"
            rec._create_manager_approval_activity()

    def action_cancel(self):
        for rec in self:
            if rec.requester_id != self.env.user:
                raise UserError(_("Only the requester can cancel this requisition."))
            if rec.state in ("po_issued", "canceled"):
                raise UserError(_("You cannot cancel a requisition that is already PO Issued or Canceled."))
            rec.state = "canceled"

    # ---------- Manager Actions ----------
    def action_manager_approve(self):
        self._validate_po_link_config()
        self._validate_scm_approver_config()

        records_need_create_rfq = self.browse()
        records_need_rfq_recheck = self.browse()
        records_need_scm_approval = self.browse()

        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted requisitions can be manager-approved."))
            if not rec.is_manager:
                raise UserError(_("Only the manager of this employee can approve at this stage."))

            rec._close_stage_activities(
                summary=_("Approve Purchase Requisition %s") % rec.name,
                feedback=_("Approved by Manager: %s") % self.env.user.name,
                strict_assigned=True,
            )

            # This review activity exists only when the PR was sent back from
            # the RFQ/SCM stage.  It is cleanup, not a mandatory approval token.
            # A normal first-time submission has only the "Approve Purchase
            # Requisition ..." activity above, so this must never block the
            # Manager Approve button or activity Mark Done.
            rec._close_stage_activities(
                summary=_("Review Purchase Requisition %s") % rec.name,
                feedback=_("Reviewed and Approved by Manager: %s") % self.env.user.name,
                strict_assigned=False,
            )

            rec.state = "rfq"

            if rec.rfq_created and rec.rfq_review_required:
                # A reset does not make an already-linked RFQ "ready" again automatically.
                # RFQ Create users must review the synchronized RFQ(s) before SCM approval.
                records_need_rfq_recheck |= rec
            elif rec.rfq_created:
                records_need_scm_approval |= rec
            else:
                records_need_create_rfq |= rec

        if records_need_create_rfq:
            records_need_create_rfq._create_po_link_activities()

        if records_need_rfq_recheck:
            records_need_rfq_recheck._create_rfq_recheck_activities()

        if records_need_scm_approval:
            records_need_scm_approval._approve_scm_activities()

    def action_manager_refuse(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted requisitions can be refused by manager."))
            if not rec.is_manager:
                raise UserError(_("Only the manager of this employee can refuse at this stage."))
            rec.state = "canceled"

    def action_manager_review(self):
        self._check_special_instruction_for_review()

        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            # ------------------------------------------------
            # Manager review from Submitted -> back to Draft
            # ------------------------------------------------
            if rec.state == "submitted":
                if not rec.is_manager:
                    raise UserError(_("Only the manager of this employee can review at this stage."))

                rec._close_stage_activities(
                    summary=_("Approve Purchase Requisition %s") % rec.name,
                    feedback=_("Sent back for review by Manager: %s") % self.env.user.name,
                )
                rec.write({"state": "draft"})
                rec._create_review_activity()
                rec._notify_users(
                    rec.requester_id,
                    _("%(pr)s was sent back to Draft by %(user)s. Please review the requested changes and resubmit. Note: %(note)s") % {
                        "pr": rec.name,
                        "user": self.env.user.display_name,
                        "note": rec.special_instruction or _("No note provided"),
                    },
                )

            # ------------------------------------------------
            # SCM / PO Link review from RFQ -> back to Submitted
            # ------------------------------------------------
            elif rec.state == "rfq":
                if rec.rfq_review_required:
                    if not rec.is_po_link:
                        raise UserError(_("Only configured RFQ Create users can send this post-reset RFQ review back."))
                    rec._close_stage_activities(
                        summary=_("Review linked RFQ(s) after reset for %s") % rec.name,
                        feedback=_("Sent back to Manager by RFQ Create user: %s") % self.env.user.name,
                        strict_assigned=False,
                    )
                elif rec.rfq_created:
                    if not rec.is_scm_approver:
                        raise UserError(_("Only configured SCM Approvers can send back after an RFQ/PO is linked."))

                    # Close the SCM approval/review activity assigned to this user.
                    rec._close_stage_activities(
                        summary=_("%s ready for SCM approval") % rec.name,
                        feedback=_("Sent back to Manager by SCM Approver: %s") % self.env.user.name,
                        strict_assigned=False,
                    )
                    rec._close_stage_activities(
                        summary=_("Review RFQ/PO & Link %s") % rec.name,
                        feedback=_("Sent back to Manager by SCM Approver: %s") % self.env.user.name,
                        strict_assigned=False,
                    )
                else:
                    if not rec.is_po_link:
                        raise UserError(_("Only configured RFQ Create users can send back before an RFQ/PO is linked."))

                    rec._close_stage_activities(
                        summary=_("Create RFQ/PO & Link %s") % rec.name,
                        feedback=_("Sent back to Manager by RFQ Create user: %s") % self.env.user.name,
                        strict_assigned=True,
                    )

                # Remove any remaining activities from both RFQ and SCM parts of the same stage.
                stage_summaries = {
                    _("Create RFQ/PO & Link %s") % rec.name,
                    _("%s ready for SCM approval") % rec.name,
                    _("Review RFQ/PO & Link %s") % rec.name,
                    _("Review linked RFQ(s) after reset for %s") % rec.name,
                }
                remaining_acts = rec.activity_ids.sudo().filtered(
                    lambda a: a.res_model == "softeko.purchase.requisition"
                    and a.res_id == rec.id
                    and a.activity_type_id.id == ActivityType.id
                    and (a.summary or "") in stage_summaries
                )
                if remaining_acts:
                    remaining_acts.with_context(
                        pr_system_activity_cleanup=True,
                        pr_skip_activity_approval_bridge=True,
                    ).action_feedback(
                        _("Closed automatically because this workflow stage is no longer active.")
                    )

                rec.write({"state": "submitted"})
                rec._create_manager_review_activity()

            else:
                raise UserError(_("Only requisitions in Submitted or RFQ stage can be sent back for review."))

    def _create_manager_review_activity(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            manager_user = rec._get_requester_manager_user()
            if not manager_user:
                continue

            summary = _("Review Purchase Requisition %s") % rec.name
            existing = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.user_id.id == manager_user.id
                and a.summary == summary
            )
            if existing:
                continue

            rec._schedule_pr_activity(
                activity_type_id=ActivityType.id,
                user_id=manager_user.id,
                summary=summary,
                note=_("%s was sent back from SCM stage for manager review.") % rec.name,
            )


    def _create_po_creation_after_so_activity(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            po_users = cfg.po_user_ids.filtered(lambda u: not u.share)
            summary = _("Issue Purchase Order for %s") % rec.name

            for user in po_users:
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=_(
                        "Sale Order confirmed for %s.\n"
                        "Please issue the Purchase Order."
                    ) % rec.name,
                )

    def _create_rfq_review_activity(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            scm_users = cfg.scm_approver_ids.filtered(lambda u: not u.share)
            summary = _("Review RFQ/PO & Link %s") % rec.name

            for user in scm_users:
                existing = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                if existing:
                    continue

                rec._schedule_pr_activity(
                    activity_type_id=ActivityType.id,
                    user_id=user.id,
                    summary=summary,
                    note=_(
                        "%s was sent back from Finance stage for RFQ/PO review."
                    ) % rec.name,
                )
    def _close_review_activity_for_requester(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            activities = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.user_id.id == rec.requester_id.id
                and (a.summary or "") == _("Requisition Review")
            )
            for activity in activities:
                activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Reviewed and resubmitted by %s") % self.env.user.name)





    # ---------- Finance Department Actions ----------
    def _check_finance_access(self):
        for rec in self:
            cfg = rec._get_approval_config()
            if not rec._user_in_users(cfg.finance_user_ids):
                raise UserError(_("You are not allowed for Finance stage for company %s. Please check Purchase Requisition → Configuration → Approval.") % (rec.company_id.display_name or self.env.company.display_name))

    def action_fd_approve(self):
        self._check_finance_access()
        self._validate_po_issuer_config()
        for rec in self:
            if rec.state != "finance_approved":
                raise UserError(_("Only Finance-stage requisitions can be approved."))
            if not rec.from_office_supply and not rec.rfq_created:
                raise UserError(_("No RFQ/PO linked yet."))

            rec._close_stage_activities(
                summary=_("PR ready for Finance approval"),
                feedback=_("Approved by Finance: %s") % self.env.user.name,
            )

            if not rec.sale_order_id:
                rec.state = "po_issued"
                rec._create_po_creation_activity()

                so_acts = rec.activity_ids.sudo().filtered(
                    lambda a: a.summary and "Confirm Sale Order" in a.summary
                )
                so_acts.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Skipped (no Sale Order)"))
                continue

            if rec.sale_order_id.state in ("sale", "done"):
                rec.state = "po_issued"
                rec._create_po_creation_after_so_activity()
                continue

            # Sale Order exists but is not confirmed yet.
            rec.state = "sale_order"
            rec._create_so_creation_activity()

    def action_fd_review(self):
        self._check_finance_access()
        self._check_special_instruction_for_review()

        for rec in self:
            if rec.state != "finance_approved":
                raise UserError(_("Only Finance-stage requisitions can be sent back for review."))

            rec._close_stage_activities(
                summary=_("PR ready for Finance approval"),
                feedback=_("Sent back to RFQ stage by Finance: %s") % self.env.user.name,
                strict_assigned=True,
            )

            rec.write({"state": "rfq"})
            rec._create_rfq_review_activity()

    def action_fd_refuse(self):
        self._check_finance_access()

        for rec in self:
            if rec.state != "rfq":
                raise UserError(_("Only PO Link-stage requisitions can be refused by Finance."))
            rec.state = "canceled"

    # ---------- RFQ Issued ----------
    def _check_scm_approval_access(self):
        for rec in self:
            cfg = rec._get_approval_config()
            if not rec._user_in_users(cfg.scm_approver_ids):
                raise UserError(_("You are not allowed to approve in SCM stage for company %s. Please check Purchase Requisition → Configuration → Approval.") % (rec.company_id.display_name or self.env.company.display_name))

    def action_mark_rfq_issued(self):
        self._check_scm_approval_access()
        self._validate_finance_config()

        for rec in self:
            if rec.state != "rfq":
                raise UserError(_("Only requisitions in the SCM Approval stage can be sent to Finance."))

            if not rec.rfq_created:
                raise UserError(_("No RFQ/PO linked yet. Please create or link an RFQ before marking as issued."))

            # Close the SCM approval activity assigned to the current SCM approver.
            rec._close_stage_activities(
                summary=_("%s ready for SCM approval") % rec.name,
                feedback=_("Approved by SCM: %s") % self.env.user.name,
                strict_assigned=True,
            )

            # close RFQ review activity coming back from finance if present
            rec._close_stage_activities(
                summary=_("Review RFQ/PO & Link %s") % rec.name,
                feedback=_("Reviewed and re-approved by SCM: %s") % self.env.user.name,
                strict_assigned=False,
            )

            # close old create RFQ activity too, if it is still open
            rec._close_stage_activities(
                summary=_("Create RFQ/PO & Link %s") % rec.name,
                feedback=_("RFQ/PO already linked earlier; approved by SCM: %s") % self.env.user.name,
                strict_assigned=False,
            )

            rec._create_finance_activities()
            rec.state = "finance_approved"

    # activity mark as done for submitted stage on click approved
    def _mark_manager_activity_done(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            manager_user = rec._get_requester_manager_user()
            if not manager_user:
                continue

            summary = _("Approve Purchase Requisition %s") % rec.name

            activities = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.user_id.id == manager_user.id
                and a.summary == summary
            )

            for activity in activities:
                activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Approved by Manager"))

    def _mark_po_link_activity_done(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            summary = _("Create RFQ/PO & Link %s") % rec.name

            activities = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.summary == summary
            )

            for activity in activities:
                activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("RFQ/PO linked to PR"))

    def _mark_finance_activity_done(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            summary = _("PR ready for Finance approval")

            activities = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.summary == summary
            )

            for activity in activities:
                activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Approved by Finance"))

    def _mark_po_creation_activity_done(self):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            summary = _("Create Purchase Order for %s") % rec.name

            activities = rec.activity_ids.sudo().filtered(
                lambda a: a.activity_type_id.id == ActivityType.id
                and a.summary == summary
            )

            for activity in activities:
                activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Purchase Order Confirmed"))

    def _mark_scm_activity_done(self):
        """
        Mark the SCM approval activity as done for this PR.
        """
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")

        for rec in self:
            cfg = rec._get_approval_config()
            scm_users = cfg.scm_approver_ids.filtered(lambda u: not u.share)
            for user in scm_users:
                summary = _("%s ready for SCM approval") % rec.name
                activities = rec.activity_ids.sudo().filtered(
                    lambda a: a.activity_type_id.id == ActivityType.id
                    and a.user_id.id == user.id
                    and a.summary == summary
                )
                for activity in activities:
                    activity.with_context(pr_system_activity_cleanup=True, pr_skip_activity_approval_bridge=True).action_feedback(_("Approved by SCM"))

    def _close_stage_activities(self, summary, feedback=None, strict_assigned=True):
        ActivityType = self.env.ref("softeko_purchase_requisition.mail_activity_type_pr_workflow")
        current_user = self.env.user

        for rec in self:
            # Keep the current user's environment while identifying/completing
            # their activity.  Starting with sudo() would bypass the PR activity
            # ownership guard in models/mail_activity.py.
            acts = rec.activity_ids.filtered(
                lambda a: a.res_model == "softeko.purchase.requisition"
                and a.res_id == rec.id
                and a.activity_type_id.id == ActivityType.id
                and (a.summary or "") == (summary or "")
            )
            if not acts:
                if strict_assigned:
                    raise UserError(_("The required approval activity was not found for this stage."))
                continue

            my_acts = acts.filtered(lambda a: a.user_id.id == current_user.id)
            other_acts = acts - my_acts

            if strict_assigned and not my_acts:
                raise UserError(_("You are not assigned to this approval activity."))

            stage_feedback = feedback or _("Approved by %s") % current_user.name

            if my_acts:
                # When approval originated from the activity's own Mark Done
                # action, that exact activity is already in Odoo's completion
                # pipeline.  Count it for strict assignment, but do not call
                # action_feedback() on it again (which would recurse).
                bridge_activity_id = self.env.context.get("pr_approval_activity_id")
                acts_to_complete = my_acts.filtered(
                    lambda a: a.id != bridge_activity_id
                )
                if acts_to_complete:
                    acts_to_complete.with_context(
                        pr_skip_activity_approval_bridge=True
                    ).action_feedback(stage_feedback)

            # Preserve the audit trail for every user who received this stage
            # activity.  When one authorized user completes the stage, close the
            # equivalent activities of the other assignees with feedback instead
            # of unlinking them.  This removes stale work from My Activities while
            # retaining the original assignment + automatic-closure history in
            # chatter. Never touch the Mark-Done source activity here; Odoo
            # completes that exact record after the business action returns.
            bridge_activity_id = self.env.context.get("pr_approval_activity_id")
            cleanup_acts = other_acts.filtered(lambda a: a.id != bridge_activity_id)
            if cleanup_acts:
                auto_feedback = _(
                    "Closed automatically because this stage was completed by %s."
                ) % current_user.name
                cleanup_acts.sudo().with_context(
                    pr_skip_activity_approval_bridge=True
                ).action_feedback(auto_feedback)

    # ---------- Product Catalog helpers ----------
    def _is_readonly(self):
        self.ensure_one()
        return self.state in ("done", "canceled")

    def action_add_from_catalog(self):
        self.ensure_one()
        res = super().action_add_from_catalog()
        # Use Purchase's catalog kanban/search because this requisition creates Purchase lines.
        res["views"][0] = (self.env.ref("purchase.product_view_kanban_catalog_purchase_only").id, "kanban")
        res["search_view_id"] = [self.env.ref("purchase.product_view_search_catalog").id, "search"]
        return res

    def _default_order_line_values(self, child_field=False):
        default_data = super()._default_order_line_values(child_field)
        new_default_data = self.env["softeko.purchase.requisition.line"]._get_product_catalog_lines_data()
        return {**default_data, **new_default_data}

    def _get_action_add_from_catalog_extra_context(self):
        return {
            **super()._get_action_add_from_catalog_extra_context(),
            "precision": self.env["decimal.precision"].precision_get("Product Unit"),
            "product_catalog_currency_id": self.currency_id.id,
            "product_catalog_digits": self.material_line_ids._fields["estimated_price"].get_digits(self.env),
            "show_sections": bool(self.id),
        }

    def _get_product_catalog_domain(self):
        return super()._get_product_catalog_domain() & Domain("purchase_ok", "=", True)

    def _get_product_catalog_order_data(self, products, **kwargs):
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            res[product.id] |= {
                "price": product.standard_price,
                "readOnly": self._is_readonly(),
                "uomDisplayName": product.uom_id.display_name,
            }
        return res

    def _get_product_catalog_record_lines(self, product_ids, *, section_id=None, **kwargs):
        grouped_lines = defaultdict(lambda: self.env["softeko.purchase.requisition.line"])
        if section_id is None:
            section_id = (
                self.material_line_ids[:1].id
                if self.material_line_ids[:1].display_type == "line_section"
                else False
            )
        for line in self.material_line_ids:
            if (
                line.display_type
                or line.product_id.id not in product_ids
                or line.get_parent_section_line().id != section_id
            ):
                continue
            grouped_lines[line.product_id] |= line
        return grouped_lines

    def _update_order_line_info(
        self, product_id, quantity, *, section_id=False, child_field="material_line_ids", **kwargs
    ):
        self.ensure_one()
        line = self.material_line_ids.filtered(
            lambda l: l.product_id.id == product_id
            and l.get_parent_section_line().id == section_id
        )
        product = self.env["product.product"].browse(product_id)

        if line:
            if quantity != 0:
                line.write({
                    "product_qty": quantity,
                    "product_uom_id": line[:1].product_uom_id.id or product.uom_id.id,
                    "categ_id": line[:1].categ_id.id or product.categ_id.id,
                })
            else:
                price = line[:1].estimated_price or product.standard_price
                line.unlink()
                return price
        elif quantity > 0:
            line = self.env["softeko.purchase.requisition.line"].create({
                "pr_requisition_id": self.id,
                "product_id": product_id,
                "name": product.display_name,
                "categ_id": product.categ_id.id,
                "product_qty": quantity,
                "product_uom_id": product.uom_id.id,
                "estimated_price": product.standard_price,
                "sequence": self._get_new_line_sequence(child_field, section_id),
            })
        return line[:1].estimated_price if line else product.standard_price

    def _get_default_create_section_values(self):
        return {"product_qty": 0.0}

    def _get_parent_field_on_child_model(self):
        return "pr_requisition_id"

    def action_create_rfq(self):
        self.ensure_one()

        if not self.material_line_ids.filtered(lambda line: not line.display_type):
            raise UserError(_("Please add at least one product line before creating an RFQ."))

        cfg = self._get_approval_config()
        allowed = cfg.link_user_ids.filtered(lambda u: u.id == self.env.user.id and not u.share)
        if not allowed and not self.env.user.has_group("base.group_system"):
            raise UserError(_("You are not allowed to create RFQ from PR."))

        default_lines = []
        for l in self.material_line_ids.sorted("sequence"):
            if l.display_type:
                default_lines.append((0, 0, {
                    "sequence": l.sequence,
                    "display_type": l.display_type,
                    "name": l.name or "",
                }))
                continue
            if not l.product_id:
                continue
            default_lines.append((0, 0, {
                "sequence": l.sequence,
                "product_id": l.product_id.id,
                "name": l.name or l.product_id.display_name,
                "product_qty": l.product_qty or 1.0,
                "product_uom_id": (l.product_uom_id or l.product_id.uom_id).id,
                "date_planned": fields.Datetime.to_datetime(l.required_date) if l.required_date else fields.Datetime.now(),
            }))

        ctx = dict(self.env.context or {})
        allowed_company_ids = list(ctx.get("allowed_company_ids") or self.env.user.company_ids.ids)
        if self.company_id.id not in allowed_company_ids:
            allowed_company_ids.append(self.company_id.id)
        ctx.update({
            "allowed_company_ids": allowed_company_ids,
            "company_id": self.company_id.id,
            "force_company": self.company_id.id,
            "default_pr_requisition_id": self.id,
            "default_pr_requisition_ids": [(6, 0, [self.id])],
            "default_origin": self.name,
            "default_order_line": default_lines,
            "default_company_id": self.company_id.id if hasattr(self, "company_id") else self.env.company.id,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Request for Quotation"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }

    @api.model
    def _get_activity_groups(self):
        """ Update the systray icon of res.partner activities to use the
        contact application one instead of base icon. """
        activities = super()._get_activity_groups()
        for activity in activities:
            if activity['model'] != 'softeko.purchase.requisition':
                continue
            activity['icon'] = modules.module.Manifest.for_addon('softeko_purchase_requisition').icon
        return activities

    def _validate_requester_manager_exists(self):
        for rec in self:
            manager_user = rec._get_requester_manager_user()
            if not manager_user:
                raise UserError(_(
                    "Cannot submit requisition %(pr)s because the requester's direct manager is not set.\n\n"
                    "Please set the Manager on the employee record of %(user)s."
                ) % {
                    "pr": rec.name or _("New"),
                    "user": rec.requester_id.name or _("the requester"),
                })

    def _validate_po_link_config(self):
        for rec in self:
            cfg = rec._get_approval_config()
            link_users = cfg.link_user_ids.filtered(lambda u: not u.share)
            if not link_users:
                raise UserError(_(
                    "RFQ Create user is not configured for company %(company)s.\n\n"
                    "Please configure at least one RFQ Create user in:\n"
                    "Purchase Requisition → Configuration → Approval."
                ) % {"company": rec.company_id.display_name or self.env.company.display_name})

    def _validate_scm_approver_config(self):
        for rec in self:
            cfg = rec._get_approval_config()
            scm_users = cfg.scm_approver_ids.filtered(lambda u: not u.share)
            if not scm_users:
                raise UserError(_(
                    "SCM Approver is not configured for company %(company)s.\n\n"
                    "Please configure at least one SCM Approver in:\n"
                    "Purchase Requisition → Configuration → Approval."
                ) % {"company": rec.company_id.display_name or self.env.company.display_name})

    def _validate_finance_config(self):
        for rec in self:
            cfg = rec._get_approval_config()
            finance_users = cfg.finance_user_ids.filtered(lambda u: not u.share)
            if not finance_users:
                raise UserError(_(
                    "Finance approver is not configured for company %(company)s.\n\n"
                    "Please configure at least one Finance user in:\n"
                    "Purchase Requisition → Configuration → Approval."
                ) % {"company": rec.company_id.display_name or self.env.company.display_name})

    def _validate_po_issuer_config(self):
        for rec in self:
            cfg = rec._get_approval_config()
            po_users = cfg.po_user_ids.filtered(lambda u: not u.share)
            if not po_users:
                raise UserError(_(
                    "PO Issuer is not configured for company %(company)s.\n\n"
                    "Please configure at least one PO Issuer user in:\n"
                    "Purchase Requisition → Configuration → Approval."
                ) % {"company": rec.company_id.display_name or self.env.company.display_name})

    def _validate_requester_exists_for_sale_order_stage(self):
        for rec in self:
            if rec.sale_order_id and not rec.requester_id:
                raise UserError(_(
                    "Cannot move requisition %(pr)s to Sale Order stage because requester is missing."
                ) % {
                    "pr": rec.name or _("New"),
                })

    def action_create_po_from_supply(self):
        self.ensure_one()

        if not self.from_office_supply:
            raise UserError(_("This action is only available for Office Supply requisitions."))

        if self.state != "po_issued":
            raise UserError(_("Purchase Order can only be created when the requisition is in PO stage."))

        if not self.is_po_issuer:
            raise UserError(_("Only configured PO Issuer users can create the Purchase Order."))

        if not self.material_line_ids.filtered(lambda line: not line.display_type):
            raise UserError(_("Please add at least one product line before creating a Purchase Order."))

        if self.rfq_created:
            raise UserError(_("An RFQ/PO is already linked to this requisition."))

        company = self.company_id or self.env.company
        warehouse = company.office_supply_warehouse_id

        if not warehouse:
            raise UserError(
                _("Office Supply Warehouse is not configured for company %s.") % company.display_name
            )

        if not warehouse.in_type_id:
            raise UserError(
                _("Receipt operation type is missing on Office Supply Warehouse for company %s.")
                % company.display_name
            )

        order_lines = []
        for line in self.material_line_ids.sorted("sequence"):
            if line.display_type:
                order_lines.append((0, 0, {
                    "sequence": line.sequence,
                    "display_type": line.display_type,
                    "name": line.name or "",
                }))
                continue

            if not line.product_id:
                continue

            order_lines.append((0, 0, {
                "sequence": line.sequence,
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "product_qty": line.product_qty,
                "product_uom_id": (line.product_uom_id or line.product_id.uom_id).id,
                "date_planned": fields.Datetime.to_datetime(line.required_date) if line.required_date else fields.Datetime.now(),
            }))

        if not order_lines:
            raise UserError(_("There are no valid material lines to create a Purchase Order."))

        ctx = dict(self.env.context or {})
        allowed_company_ids = list(ctx.get("allowed_company_ids") or self.env.user.company_ids.ids)
        if company.id not in allowed_company_ids:
            allowed_company_ids.append(company.id)
        ctx.update({
            "allowed_company_ids": allowed_company_ids,
            "company_id": company.id,
            "force_company": company.id,
            "default_pr_requisition_id": self.id,
            "default_pr_requisition_ids": [(6, 0, [self.id])],
            "default_origin": self.name,
            "default_company_id": company.id,
            "default_picking_type_id": warehouse.in_type_id.id,
            "default_order_line": order_lines,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "target": "current",
            "context": ctx,
        }