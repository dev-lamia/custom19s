from odoo import fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _validate_requirement_item_code_inputs(self):
        """Validate raw-material coding inputs before PO confirmation."""
        for order in self:
            for line in order.order_line.filtered(
                lambda rec: not rec.display_type and rec.product_id
            ):
                template = line.product_id.product_tmpl_id
                if not template._is_requirement_raw_material():
                    continue
                if not template.requirement_category_type_id:
                    raise ValidationError(
                        _(
                            'Set a Type on raw-material product "%s" before '
                            'confirming the Purchase Order.'
                        )
                        % template.display_name
                    )
        return True

    def _get_or_create_item_code_sequence(
        self,
        supplier_initial,
        category_initial,
        company,
    ):
        """Return a company-specific sequence for one supplier/type prefix."""
        sequence_code = (
            'crm_requirement_form.item_code.'
            f'{supplier_initial}.{category_initial}.{company.id}'
        )
        sequence_model = self.env['ir.sequence'].sudo()
        sequence = sequence_model.search(
            [
                ('code', '=', sequence_code),
                ('company_id', '=', company.id),
            ],
            limit=1,
        )
        if not sequence:
            sequence = sequence_model.create({
                'name': _(
                    'Raw Material Item Code %s-%s'
                ) % (supplier_initial, category_initial),
                'code': sequence_code,
                'padding': 2,
                'number_increment': 1,
                'company_id': company.id,
            })
        return sequence

    def _generate_requirement_item_codes(self):
        """Generate a fresh Item Code on every PO confirmation.

        The code belongs to the Purchase Order Line, not to product.template.
        Every confirmation consumes the next sequence number, even when the
        same product was purchased before.

        Format: Supplier Initial - Raw Material Type Initial - Incremental Series
        Example: 02-04-01, 02-04-02, 02-04-03
        """
        for order in self:
            supplier_initial = '02'

            for line in order.order_line.filtered(
                lambda rec: not rec.display_type and rec.product_id
            ):
                template = line.product_id.product_tmpl_id
                if not template._is_requirement_raw_material():
                    continue

                category_type = template.requirement_category_type_id
                if not category_type:
                    continue

                category_initial = f'{category_type.category_initial:02d}'
                sequence = order._get_or_create_item_code_sequence(
                    supplier_initial,
                    category_initial,
                    order.company_id,
                )
                serial = sequence.next_by_id()
                item_code = f'{supplier_initial}-{category_initial}-{serial}'
                line.sudo().write({
                    'requirement_item_code': item_code,
                })
                self.env['purchase.item.code'].sudo().create({
                    'name': item_code,
                    'purchase_order_line_id': line.id,
                    'product_id': line.product_id.id,
                    'category_type_id': category_type.id,
                    'supplier_initial': supplier_initial,
                    'category_initial': category_type.category_initial,
                    'company_id': order.company_id.id,
                })
        return True

    def button_confirm(self):
        self._validate_requirement_item_code_inputs()
        result = super().button_confirm()
        self._generate_requirement_item_codes()
        return result


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    requirement_item_code = fields.Char(
        string='Item Code',
        copy=False,
        readonly=True,
        index=True,
        help=(
            'Generated every time the Purchase Order is confirmed. '
            'Format: 02-Type Initial-Incremental Series.'
        ),
    )

class PurchaseItemCode(models.Model):
    _name = 'purchase.item.code'
    _description = 'Purchase Item Code'
    _order = 'generated_on desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Item Code',
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    purchase_order_line_id = fields.Many2one(
        'purchase.order.line',
        string='Purchase Order Line',
        required=True,
        readonly=True,
        ondelete='cascade',
        index=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        related='purchase_order_line_id.order_id',
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        related='purchase_order_id.partner_id',
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        readonly=True,
        ondelete='restrict',
        index=True,
    )
    category_type_id = fields.Many2one(
        'product.category.type',
        string='Raw Material Type',
        required=True,
        readonly=True,
        ondelete='restrict',
        index=True,
    )
    supplier_initial = fields.Char(
        string='Supplier Initial',
        required=True,
        readonly=True,
    )
    category_initial = fields.Integer(
        string='Category Initial',
        required=True,
        readonly=True,
    )
    generated_on = fields.Datetime(
        string='Generated On',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        ondelete='restrict',
        index=True,
    )

    _sql_constraints = [
        (
            'purchase_item_code_name_company_uniq',
            'unique(name, company_id)',
            'Item Code must be unique per company.',
        ),
    ]

