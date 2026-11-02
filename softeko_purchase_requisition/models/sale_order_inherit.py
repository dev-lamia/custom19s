from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    pr_count = fields.Integer(string="PR Count", compute="_compute_pr_count")

    def _compute_pr_count(self):
        PR = self.env["softeko.purchase.requisition"].sudo()
        for so in self:
            so.pr_count = PR.search_count([("sale_order_id", "=", so.id)])

    def _prepare_purchase_requisition_line_values(self, sol):
        vals = {
            "sequence": sol.sequence,
            "sale_line_id": sol.id,
            "display_type": sol.display_type,
            "name": sol.name,
        }

        if sol.display_type:
            vals.update({"product_qty": 0.0})
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

    def action_create_purchase_requisition(self):
        self.ensure_one()
        allowed_company_ids = list(self.env.context.get("allowed_company_ids") or self.env.user.company_ids.ids)
        if self.company_id.id not in allowed_company_ids:
            allowed_company_ids.append(self.company_id.id)

        PR = self.env["softeko.purchase.requisition"].with_company(self.company_id).with_context(
            allowed_company_ids=allowed_company_ids,
            company_id=self.company_id.id,
            force_company=self.company_id.id,
        )

        # Create PR and preserve Sale Order sections, notes, and line descriptions.
        line_cmds = []
        for sol in self.order_line.sorted("sequence"):
            vals = self._prepare_purchase_requisition_line_values(sol)
            if vals:
                line_cmds.append((0, 0, vals))

        pr = PR.create({
            "requester_id": self.env.user.id,
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
            "material_line_ids": line_cmds,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Requisition"),
            "res_model": "softeko.purchase.requisition",
            "view_mode": "form",
            "res_id": pr.id,
            "target": "current",
        }

    def action_view_purchase_requisitions(self):
        self.ensure_one()
        allowed_company_ids = list(self.env.context.get("allowed_company_ids") or self.env.user.company_ids.ids)
        if self.company_id.id not in allowed_company_ids:
            allowed_company_ids.append(self.company_id.id)

        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Requisitions"),
            "res_model": "softeko.purchase.requisition",
            "view_mode": "kanban,list,form",
            "domain": [("sale_order_id", "=", self.id)],
            "context": {
                "default_sale_order_id": self.id,
                "default_company_id": self.company_id.id,
                "allowed_company_ids": allowed_company_ids,
                "company_id": self.company_id.id,
                "force_company": self.company_id.id,
            },
        }

    def action_confirm(self):
        # Call the original confirmation logic first.
        res = super().action_confirm()

        # Now handle linked Purchase Requisitions.
        PR = self.env["softeko.purchase.requisition"].sudo()
        for so in self:
            prs = PR.search([("sale_order_id", "=", so.id), ("state", "=", "sale_order")])
            for pr in prs:
                pr._check_sale_order_confirmation()

        return res
