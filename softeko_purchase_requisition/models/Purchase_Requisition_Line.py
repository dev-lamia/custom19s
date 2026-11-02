from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequisitionLine(models.Model):
    _name = "softeko.purchase.requisition.line"
    _description = "Purchase Requisition Line"
    _order = "pr_requisition_id, sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    display_type = fields.Selection(
        [
            ("line_section", "Section"),
            ("line_subsection", "Subsection"),
            ("line_note", "Note"),
        ],
        default=False,
        help="Technical field for section and note lines.",
    )
    name = fields.Text(string="Description")

    pr_requisition_id = fields.Many2one(
        "softeko.purchase.requisition",
        string="Purchase Requisition",
        required=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="pr_requisition_id.currency_id",
        readonly=True,
    )

    # Link back to SO line, so the origin is visible and the SO description can be preserved.
    sale_line_id = fields.Many2one("sale.order.line", string="Sale Order Line", readonly=True)

    categ_id = fields.Many2one("product.category", string="Category")
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )
    product_type = fields.Selection(
        related="product_id.type",
        readonly=True,
        string="Product Type",
    )
    product_qty = fields.Float(string="Quantity", default=1.0)

    # Odoo product catalog expects this field name, same as sale/purchase lines.
    # Keep it synchronized with this module's existing product_qty field.
    product_uom_qty = fields.Float(
        string="Catalog Quantity",
        compute="_compute_product_uom_qty",
        inverse="_inverse_product_uom_qty",
        store=True,
    )

    product_uom_id = fields.Many2one("uom.uom", string="UoM", readonly=True)
    required_date = fields.Date(string="Required Delivery Date")
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "Low"),
            ("2", "High"),
            ("3", "Urgent"),
        ],
        string="Priority Level",
        default="0",
    )

    estimated_price = fields.Float(string="Estimated Price")
    sales_currency_id = fields.Many2one(
        "res.currency",
        string="Sales Currency",
        readonly=True,
        copy=False,
        help=(
            "Currency used for Sales Price. It is taken from the linked RFQ/PO "
            "line used for the price calculation."
        ),
    )
    sales_price = fields.Monetary(
        string="Sales Price",
        currency_field="sales_currency_id",
        readonly=True,
        copy=False,
        help=(
            "Updated from the average RFQ/purchase unit price for this product "
            "plus the product margin, in the Sales Currency."
        ),
    )
    parent_id = fields.Many2one(
        "softeko.purchase.requisition.line",
        string="Parent Section Line",
        compute="_compute_parent_id",
    )

    @api.depends("product_qty")
    def _compute_product_uom_qty(self):
        for line in self:
            line.product_uom_qty = line.product_qty

    def _inverse_product_uom_qty(self):
        for line in self:
            line.product_qty = line.product_uom_qty

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("display_type"):
            res.setdefault("product_qty", 0.0)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env["product.product"]
        for vals in vals_list:
            if vals.get("display_type"):
                vals.update(self._get_display_type_clear_values())
            elif vals.get("product_id"):
                product = Product.browse(vals["product_id"])
                if not vals.get("name"):
                    vals["name"] = product.display_name
                if not vals.get("categ_id"):
                    vals["categ_id"] = product.categ_id.id
                if not vals.get("product_uom_id"):
                    vals["product_uom_id"] = product.uom_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("display_type"):
            vals = dict(vals, **self._get_display_type_clear_values())

        res = super().write(vals)

        # Catalog/server writes do not trigger onchange, so keep UoM filled from product.
        if "product_id" in vals or "product_qty" in vals or "product_uom_qty" in vals:
            for line in self.filtered(lambda l: not l.display_type and l.product_id and not l.product_uom_id):
                line.product_uom_id = line.product_id.uom_id.id

        return res

    @api.constrains("display_type", "product_id", "product_qty")
    def _check_required_product_lines(self):
        for line in self:
            if line.display_type:
                continue
            if not line.product_id:
                raise ValidationError(_("Please select a product on every product line."))
            if line.product_qty <= 0:
                raise ValidationError(_("Quantity must be greater than zero on product lines."))

    def _get_display_type_clear_values(self):
        return {
            "product_id": False,
            "categ_id": False,
            "product_qty": 0.0,
            "product_uom_id": False,
            "required_date": False,
            "estimated_price": 0.0,
            "sales_price": 0.0,
            "sales_currency_id": False,
        }

    def action_open_delivery_schedule(self):
        self.ensure_one()
        if self.display_type:
            raise UserError(_("Delivery schedule is only available for product lines."))
        Delivery = self.env["softeko.purchase.requisition.delivery"]
        schedule = Delivery.search([("line_id", "=", self.id)], limit=1)
        if not schedule:
            schedule = Delivery.create({"line_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Schedule"),
            "res_model": "softeko.purchase.requisition.delivery",
            "view_mode": "form",
            "res_id": schedule.id,
            "target": "new",
        }

    @api.onchange("display_type")
    def _onchange_display_type(self):
        for line in self:
            if line.display_type:
                line.product_id = False
                line.categ_id = False
                line.product_qty = 0.0
                line.product_uom_id = False
                line.required_date = False
                line.estimated_price = 0.0
                line.sales_price = 0.0
                line.sales_currency_id = False

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.categ_id = line.product_id.categ_id
                line.product_uom_id = line.product_id.uom_id
                # This is the description shown by the same widget used on Sales/Purchase lines.
                line.name = line.product_id.display_name
            elif not line.display_type:
                line.categ_id = False
                line.product_uom_id = False

    @api.onchange("sale_line_id")
    def _onchange_sale_line_id(self):
        for line in self:
            if line.sale_line_id:
                sol = line.sale_line_id
                line.display_type = sol.display_type
                line.name = sol.name
                if sol.display_type:
                    line.product_id = False
                    line.categ_id = False
                    line.product_qty = 0.0
                    line.product_uom_id = False
                else:
                    line.product_id = sol.product_id
                    line.categ_id = sol.product_id.categ_id
                    line.product_qty = sol.product_uom_qty
                    line.product_uom_id = sol.product_uom_id


    # ---------- Sales price helpers ----------
    def _get_margin_value_from_product(self, product):
        """Return the configured product margin, without hard dependency on Pre-Sale."""
        if not product:
            return 0.0

        tmpl = product.product_tmpl_id
        for field_name in (
            "margin_cost",
            "presale_margin_cost_percent",
            "margin_percent",
            "presale_margin_percent",
            "x_margin_cost",
        ):
            if tmpl and field_name in tmpl._fields:
                return tmpl[field_name] or 0.0

        if "margin.based.category" in self.env:
            margin_model = self.env["margin.based.category"].sudo()
            margin_field = "margin_cost"
            if margin_field in margin_model._fields:
                for field_name in (
                    "product_ids",
                    "product_tmpl_ids",
                    "product_template_ids",
                    "product_product_ids",
                ):
                    field = margin_model._fields.get(field_name)
                    if not field:
                        continue
                    search_ids = product.ids
                    if field.comodel_name == "product.template":
                        search_ids = tmpl.ids
                    category = margin_model.search([(field_name, "in", search_ids)], limit=1)
                    if category:
                        return category[margin_field] or 0.0

        return 0.0

    def _get_margin_factor(self, margin_value):
        """Accept both 10 (=10%) and 0.10 (=10%) margin formats."""
        margin_value = margin_value or 0.0
        return margin_value / 100.0 if abs(margin_value) > 1.0 else margin_value

    def _get_purchase_line_uom(self, purchase_line):
        if "product_uom_id" in purchase_line._fields:
            return purchase_line.product_uom_id
        if "product_uom" in purchase_line._fields:
            return purchase_line.product_uom
        return purchase_line.product_id.uom_id

    def _get_purchase_line_currency(self, purchase_line):
        if "currency_id" in purchase_line._fields and purchase_line.currency_id:
            return purchase_line.currency_id
        if purchase_line.order_id and purchase_line.order_id.currency_id:
            return purchase_line.order_id.currency_id
        return self.env.company.currency_id

    def _get_linked_purchase_lines_for_sales_price(self):
        self.ensure_one()
        if not self.pr_requisition_id or not self.product_id:
            return self.env["purchase.order.line"]

        purchase_orders = self.pr_requisition_id.purchase_order_ids.filtered(lambda po: po.state != "cancel")
        if not purchase_orders:
            return self.env["purchase.order.line"]

        domain = [
            ("order_id", "in", purchase_orders.ids),
            ("product_id", "=", self.product_id.id),
        ]
        PurchaseLine = self.env["purchase.order.line"].sudo()
        if "display_type" in PurchaseLine._fields:
            domain.append(("display_type", "=", False))

        return PurchaseLine.search(domain, order="order_id, id")

    def _get_sales_price_target_currency(self, purchase_lines):
        """Use the linked RFQ/PO currency for Sales Price.

        This prevents the Sales Price monetary widget from falling back to the
        PR/company currency, e.g. showing AED when the RFQ/PO is in USD. If
        several RFQ currencies are present, the first linked RFQ/PO currency is
        used and the other RFQ prices are converted before averaging.
        """
        self.ensure_one()
        for purchase_line in purchase_lines:
            currency = self._get_purchase_line_currency(purchase_line)
            if currency:
                return currency

        sale_currency = self.pr_requisition_id.sale_order_id.currency_id if self.pr_requisition_id.sale_order_id else False
        return sale_currency or self.currency_id or self.pr_requisition_id.currency_id or self.env.company.currency_id

    def _get_purchase_line_unit_price_in_currency(self, purchase_line, target_currency):
        self.ensure_one()
        price = purchase_line.price_unit or 0.0

        source_currency = self._get_purchase_line_currency(purchase_line)
        target_currency = target_currency or source_currency
        company = self.pr_requisition_id.company_id or purchase_line.order_id.company_id or self.env.company
        conversion_date = fields.Date.to_date(purchase_line.order_id.date_order) or fields.Date.context_today(self)

        if source_currency and target_currency and source_currency != target_currency:
            price = source_currency._convert(price, target_currency, company, conversion_date)

        source_uom = self._get_purchase_line_uom(purchase_line)
        target_uom = self.product_uom_id or self.product_id.uom_id
        if source_uom and target_uom and source_uom != target_uom and source_uom.category_id == target_uom.category_id:
            price = source_uom._compute_price(price, target_uom)

        return price

    def _get_average_purchase_unit_price_and_currency(self):
        self.ensure_one()
        purchase_lines = self._get_linked_purchase_lines_for_sales_price()
        if not purchase_lines:
            return 0.0, False

        target_currency = self._get_sales_price_target_currency(purchase_lines)
        prices = [
            self._get_purchase_line_unit_price_in_currency(purchase_line, target_currency)
            for purchase_line in purchase_lines
        ]
        return (sum(prices) / len(prices) if prices else 0.0), target_currency

    def _get_average_purchase_unit_price(self):
        """Backward compatible helper: return only the average price."""
        average_price, _currency = self._get_average_purchase_unit_price_and_currency()
        return average_price

    def _update_sales_price_from_rfq_unit_prices(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.sales_price = 0.0
                line.sales_currency_id = False
                continue

            average_purchase_price, target_currency = line._get_average_purchase_unit_price_and_currency()
            margin_value = line._get_margin_value_from_product(line.product_id)
            line.sales_currency_id = target_currency.id if target_currency else False
            line.sales_price = average_purchase_price * (1.0 + line._get_margin_factor(margin_value))

    def action_add_from_catalog(self):
        order_id = self.env.context.get("order_id")
        if not order_id:
            raise UserError(_("Please save the requisition before using the catalog."))
        requisition = self.env["softeko.purchase.requisition"].browse(order_id)
        return requisition.with_context(child_field="material_line_ids").action_add_from_catalog()

    def _get_product_catalog_lines_data(self, **kwargs):
        if len(self) == 1:
            self.ensure_one()
            return {
                "quantity": self.product_qty,
                "price": self.estimated_price,
                "readOnly": self.pr_requisition_id._is_readonly(),
                "uomDisplayName": self.product_uom_id.display_name or self.product_id.uom_id.display_name,
            }
        elif self:
            product = self.product_id
            product.ensure_one()
            order_line = self[0]
            return {
                "quantity": sum(self.mapped("product_qty")),
                "price": order_line.estimated_price,
                "readOnly": True,
                "uomDisplayName": product.uom_id.display_name,
            }
        return {"quantity": 0}

    def _compute_parent_id(self):
        requisition_lines = set(self)
        for requisition, lines in self.grouped("pr_requisition_id").items():
            if not requisition:
                lines.parent_id = False
                continue
            last_section = False
            last_sub = False
            for line in requisition.material_line_ids.sorted("sequence"):
                if line.display_type == "line_section":
                    last_section = line
                    if line in requisition_lines:
                        line.parent_id = False
                    last_sub = False
                elif line.display_type == "line_subsection":
                    if line in requisition_lines:
                        line.parent_id = last_section
                    last_sub = line
                elif line in requisition_lines:
                    line.parent_id = last_sub or last_section

    def get_parent_section_line(self):
        self.ensure_one()
        if not self.display_type and self.parent_id.display_type == "line_subsection":
            return self.parent_id.parent_id
        return self.parent_id
