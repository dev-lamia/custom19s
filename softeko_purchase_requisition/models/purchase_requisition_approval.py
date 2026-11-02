# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PurchaseRequisitionApproval(models.Model):
    _name = "softeko.purchase.requisition.approval"
    _description = "Purchase Requisition Approval Configuration"
    _rec_name = "name"

    name = fields.Char(default="Approval Configuration", required=True)

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        ondelete="cascade",
    )

    # ----------------------------
    # Configurable stage access
    # ----------------------------

    link_user_ids = fields.Many2many(
        "res.users",
        "pr_approval_link_user_rel",
        "config_id",
        "user_id",
        string="RFQ Create",
        help="Users allowed to create RFQ / PO and link Purchase Requisitions.",
    )

    scm_approver_ids = fields.Many2many(
        "res.users",
        "pr_approval_scm_approver_rel",
        "config_id",
        "user_id",
        string="SCM Approvers",
        help="Users allowed to approve the requisition after an RFQ / PO has been linked.",
    )

    finance_user_ids = fields.Many2many(
        "res.users",
        "pr_approval_fin_user_rel",
        "config_id",
        "user_id",
        string="Finance Approvers",
    )

    po_user_ids = fields.Many2many(
        "res.users",
        "pr_approval_po_user_rel",
        "config_id",
        "user_id",
        string="PO Issuers",
    )

    no_manager_approval_employee_ids = fields.Many2many(
        "hr.employee",
        "pr_approval_no_manager_employee_rel",
        "config_id",
        "employee_id",
        string="No Manager Approval Employees",
        domain=[("user_id", "!=", False)],
        help=(
            "Employees selected here bypass Manager Approval for Purchase Requisitions "
            "belonging to this configuration's company. On submit, their PR moves "
            "directly to the RFQ/PO Link stage. The employee's HR manager is unchanged."
        ),
    )

    _sql_constraints = [
        (
            "uniq_company_config",
            "unique(company_id)",
            "Only one Approval Configuration is allowed per company.",
        ),
    ]

    @api.constrains("company_id")
    def _check_unique_company_config(self):
        """Enforce one approval configuration per company at ORM level too.

        Keep this in addition to the SQL constraint.  It protects Create and
        Duplicate even on databases where an older duplicate prevented the SQL
        unique constraint from being installed during an earlier upgrade.
        """
        for rec in self:
            if not rec.company_id:
                continue
            duplicate = self.sudo().search([
                ("company_id", "=", rec.company_id.id),
                ("id", "!=", rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("Only one Approval Configuration is allowed for company %s.")
                    % rec.company_id.display_name
                )

    # ----------------------------
    # Helpers
    # ----------------------------
    @api.model
    def get_company_config(self, company=None):
        """Return the approval configuration for ``company`` if configured.

        The configuration menu now uses a normal list/form action.  Do not
        auto-create records while merely reading workflow configuration.
        """
        company = company or self.env.company
        return self.sudo().search([("company_id", "=", company.id)], limit=1)

