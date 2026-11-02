# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    pr_access_scope = fields.Selection(
        [
            ("own", "No"),
            ("team", "Team Approver"),
            ("admin", "Admin"),
        ],
        string="Purchase Requisition",
        default="own",
        help=(
            "No: user can see only own purchase requisitions.\n"
            "Team Approver: user can see own requisitions and requisitions of employees reporting to them.\n"
            "Admin: user can see all purchase requisitions."
        ),
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_pr_access_groups()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "pr_access_scope" in vals and not self.env.context.get("skip_pr_group_sync"):
            self._sync_pr_access_groups()
        return res

    def _sync_pr_access_groups(self):
        group_own = self.env.ref("softeko_purchase_requisition.group_pr_own", raise_if_not_found=False)
        group_team = self.env.ref("softeko_purchase_requisition.group_pr_team", raise_if_not_found=False)
        group_admin = self.env.ref("softeko_purchase_requisition.group_pr_admin", raise_if_not_found=False)

        if not all([group_own, group_team, group_admin]):
            return

        for user in self:
            scope = user.pr_access_scope or "own"

            cmds = [
                (3, group_own.id),
                (3, group_team.id),
                (3, group_admin.id),
            ]

            if scope == "team":
                cmds.append((4, group_team.id))
            elif scope == "admin":
                cmds.append((4, group_admin.id))
            else:
                cmds.append((4, group_own.id))

            super(ResUsers, user.with_context(skip_pr_group_sync=True).sudo()).write({
                "group_ids": cmds,
            })