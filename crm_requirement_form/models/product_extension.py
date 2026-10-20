import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    thickness_microns = fields.Float(
        string='Thickness (Microns)',
        help='Optional default thickness used in CRM requirement form layers.',
    )

    # Kept as the legacy stored Bag flag so existing databases upgrade safely.
    # The Product form now exposes the FG Type checkboxes below instead.
    is_requirement_bag_type = fields.Boolean(
        string='Legacy Bag FG Product',
        help='Legacy flag retained for backward compatibility.',
        index=True,
    )
    is_requirement_roll_type = fields.Boolean(
        string='Roll FG Product',
        help='Technical stored flag used for Roll finished-goods products.',
        index=True,
    )
    requirement_fg_type_id = fields.Many2one(
        'crm.requirement.fg.type',
        string='FG Type',
        domain=[('active', '=', True)],
        index=True,
        ondelete='restrict',
        help=(
            'Configurable finished-goods type. New FG Types can be created '
            'from Requirement Configuration > FG Types.'
        ),
    )
    requirement_category_type_id = fields.Many2one(
        'product.category.type',
        string='Type',
        domain=[('active', '=', True)],
        ondelete='restrict',
        index=True,
        help=(
            'Raw-material type used when the Product Category is Raw Materials. '
            'The Category Initial is maintained on the selected Type.'
        ),
    )
    requirement_category_initial = fields.Integer(
        string='Category Initial',
        related='requirement_category_type_id.category_initial',
        store=True,
        readonly=True,
    )
    show_requirement_category_type = fields.Boolean(
        string='Show Raw Material Type',
        compute='_compute_show_requirement_category_type',
    )
    requirement_fg_type = fields.Selection(
        [
            ('bag', 'Bag'),
            ('roll', 'Roll'),
        ],
        string='FG Type',
        compute='_compute_requirement_fg_type',
        store=True,
        index=True,
        help='Finished-goods classification used to filter Sale Order products.',
    )
    requirement_fg_bag = fields.Boolean(
        string='Bag',
        compute='_compute_requirement_fg_type_checks',
        inverse='_inverse_requirement_fg_bag',
        help='Select this checkbox to make the product available for Bag FG lines.',
    )
    requirement_fg_roll = fields.Boolean(
        string='Roll',
        compute='_compute_requirement_fg_type_checks',
        inverse='_inverse_requirement_fg_roll',
        help='Select this checkbox to make the product available for Roll FG lines.',
    )
    is_requirement_layer = fields.Boolean(
        string='Layer',
        help=(
            'Select this checkbox to make the product available in the '
            'Requirement Form Layer dropdowns.'
        ),
        index=True,
    )
    requirement_bag_type_code = fields.Char(
        string='FG Type Code',
        help=(
            'Code used in the GDN Number for this FG product, for example '
            'FB, SUP, QS, 3SS, 2SS, LBL, or RS.'
        ),
        copy=False,
        index=True,
    )
    requirement_hide_gusset = fields.Boolean(
        string='Hide Gusset for FG Product',
        compute='_compute_requirement_hide_gusset',
        help=(
            'Automatically hides Gusset for Roll products and for Bag codes '
            'containing SS or starting with L.'
        ),
    )
    requirement_item_code_count = fields.Integer(
        string='Item Codes',
        compute='_compute_requirement_item_code_count',
        help='Number of generated Purchase Item Codes for this product.',
    )

    def _compute_requirement_item_code_count(self):
        counts = {template_id: 0 for template_id in self.ids}
        if self.ids:
            item_codes = self.env['purchase.item.code'].search([
                ('product_id.product_tmpl_id', 'in', self.ids),
            ])
            for item_code in item_codes:
                template_id = item_code.product_id.product_tmpl_id.id
                if template_id in counts:
                    counts[template_id] += 1
        for product in self:
            product.requirement_item_code_count = counts.get(product.id, 0)

    def action_open_requirement_item_codes(self):
        self.ensure_one()
        action = self.env.ref(
            'crm_requirement_form.action_purchase_item_code'
        ).read()[0]
        action['domain'] = [
            ('product_id.product_tmpl_id', '=', self.id),
        ]
        action['context'] = {
            'search_default_group_purchase_order': 1,
        }
        return action

    @api.depends('categ_id', 'categ_id.name')
    def _compute_show_requirement_category_type(self):
        for product in self:
            category_name = (product.categ_id.name or '').strip().casefold()
            product.show_requirement_category_type = (
                category_name == 'raw materials'
            )

    @api.onchange('categ_id')
    def _onchange_requirement_category_type(self):
        for product in self:
            category_name = (product.categ_id.name or '').strip().casefold()
            if category_name != 'raw materials':
                product.requirement_category_type_id = False

    @api.depends(
        'requirement_fg_type_id.behavior',
        'is_requirement_bag_type',
        'is_requirement_roll_type',
        'requirement_bag_type_code',
    )
    def _compute_requirement_fg_type(self):
        """Classify old and new records without requiring a data migration.

        Older module versions stored Roll Stock/Label as Bag Type products with
        codes RS/LBL. Treat those legacy rows as Roll automatically so existing
        databases immediately work after module upgrade.
        """
        for product in self:
            code = (product.requirement_bag_type_code or '').strip().upper()
            if product.requirement_fg_type_id:
                product.requirement_fg_type = (
                    product.requirement_fg_type_id.behavior or False
                )
            elif product.is_requirement_roll_type:
                product.requirement_fg_type = 'roll'
            elif product.is_requirement_bag_type:
                product.requirement_fg_type = (
                    'roll' if code in {'RS', 'LBL'} else 'bag'
                )
            else:
                product.requirement_fg_type = False

    @api.depends('requirement_fg_type')
    def _compute_requirement_fg_type_checks(self):
        for product in self:
            product.requirement_fg_bag = product.requirement_fg_type == 'bag'
            product.requirement_fg_roll = product.requirement_fg_type == 'roll'

    def _inverse_requirement_fg_bag(self):
        for product in self:
            if product.requirement_fg_bag:
                product.is_requirement_bag_type = True
                product.is_requirement_roll_type = False
            elif product.requirement_fg_type == 'bag':
                product.is_requirement_bag_type = False

    def _inverse_requirement_fg_roll(self):
        for product in self:
            if product.requirement_fg_roll:
                product.is_requirement_roll_type = True
                product.is_requirement_bag_type = False
            elif product.requirement_fg_type == 'roll':
                product.is_requirement_roll_type = False
                product.is_requirement_bag_type = False

    @api.onchange('requirement_fg_type_id')
    def _onchange_requirement_fg_type_id(self):
        for product in self:
            behavior = product.requirement_fg_type_id.behavior
            product.is_requirement_bag_type = behavior == 'bag'
            product.is_requirement_roll_type = behavior == 'roll'

    @api.onchange('requirement_fg_bag')
    def _onchange_requirement_fg_bag(self):
        if self.requirement_fg_bag:
            self.requirement_fg_roll = False
            self.is_requirement_bag_type = True
            self.is_requirement_roll_type = False
        elif self.requirement_fg_type == 'bag':
            self.is_requirement_bag_type = False

    @api.onchange('requirement_fg_roll')
    def _onchange_requirement_fg_roll(self):
        if self.requirement_fg_roll:
            self.requirement_fg_bag = False
            self.is_requirement_roll_type = True
            self.is_requirement_bag_type = False
        elif self.requirement_fg_type == 'roll':
            self.is_requirement_roll_type = False
            self.is_requirement_bag_type = False

    @api.depends('requirement_fg_type', 'requirement_bag_type_code')
    def _compute_requirement_hide_gusset(self):
        for product in self:
            code = (product.requirement_bag_type_code or '').strip().upper()
            product.requirement_hide_gusset = bool(
                product.requirement_fg_type == 'roll'
                or (
                    product.requirement_fg_type == 'bag'
                    and ('SS' in code or code.startswith('L'))
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = []
        fg_type_model = self.env['crm.requirement.fg.type']
        for vals in vals_list:
            vals = dict(vals)
            fg_type_id = vals.get('requirement_fg_type_id')
            if fg_type_id:
                behavior = fg_type_model.browse(fg_type_id).behavior
                vals['is_requirement_bag_type'] = behavior == 'bag'
                vals['is_requirement_roll_type'] = behavior == 'roll'
            elif vals.get('is_requirement_roll_type'):
                vals['is_requirement_bag_type'] = False
            elif vals.get('is_requirement_bag_type'):
                vals['is_requirement_roll_type'] = False
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)

    def write(self, vals):
        result = True
        fg_type_model = self.env['crm.requirement.fg.type']
        for product in self:
            product_vals = dict(vals)
            if 'requirement_fg_type_id' in product_vals:
                fg_type_id = product_vals.get('requirement_fg_type_id')
                if fg_type_id:
                    behavior = fg_type_model.browse(fg_type_id).behavior
                    product_vals['is_requirement_bag_type'] = behavior == 'bag'
                    product_vals['is_requirement_roll_type'] = behavior == 'roll'
                else:
                    product_vals['is_requirement_bag_type'] = False
                    product_vals['is_requirement_roll_type'] = False
            elif product_vals.get('is_requirement_roll_type'):
                product_vals['is_requirement_bag_type'] = False
            elif product_vals.get('is_requirement_bag_type'):
                product_vals['is_requirement_roll_type'] = False
            elif (
                product.is_requirement_bag_type
                and product.is_requirement_roll_type
            ):
                product_vals['is_requirement_bag_type'] = False
            result = super(ProductTemplate, product).write(product_vals) and result
        return result

    @api.model
    def _backfill_requirement_fg_type_id(self):
        """Link legacy Bag/Roll flags to the new configurable FG Type."""
        bag_type = self.env.ref(
            'crm_requirement_form.requirement_fg_type_bag',
            raise_if_not_found=False,
        )
        roll_type = self.env.ref(
            'crm_requirement_form.requirement_fg_type_roll',
            raise_if_not_found=False,
        )
        if not bag_type or not roll_type:
            return True

        products = self.search([('requirement_fg_type_id', '=', False)])
        for product in products:
            code = (product.requirement_bag_type_code or '').strip().upper()
            if product.is_requirement_roll_type or (
                product.is_requirement_bag_type and code in {'RS', 'LBL'}
            ):
                product.write({'requirement_fg_type_id': roll_type.id})
            elif product.is_requirement_bag_type:
                product.write({'requirement_fg_type_id': bag_type.id})
        return True

    @api.constrains(
        'is_requirement_bag_type',
        'is_requirement_roll_type',
        'requirement_bag_type_code',
    )
    def _check_requirement_fg_configuration(self):
        for product in self:
            if product.is_requirement_bag_type and product.is_requirement_roll_type:
                raise ValidationError(
                    _('A product can be either Bag or Roll FG Type, not both.')
                )
            if (
                (product.is_requirement_bag_type or product.is_requirement_roll_type)
                and not (product.requirement_bag_type_code or '').strip()
            ):
                raise ValidationError(
                    _('FG Type Code is required for a Bag or Roll FG product.')
                )

    @api.onchange('requirement_bag_type_code')
    def _onchange_requirement_bag_type_code(self):
        if self.requirement_bag_type_code:
            self.requirement_bag_type_code = (
                self.requirement_bag_type_code.strip().upper()
            )

    def _get_requirement_bag_code(self):
        """Return the GDN code for any configured finished-goods product."""
        self.ensure_one()
        if not self.requirement_fg_type:
            return False
        return (self.requirement_bag_type_code or '').strip().upper() or False

    def _requirement_should_hide_gusset(self):
        self.ensure_one()
        if self.requirement_fg_type == 'roll':
            return True
        code = self._get_requirement_bag_code() or ''
        return 'SS' in code or code.startswith('L')


    def _is_requirement_raw_material(self):
        self.ensure_one()
        category = self.categ_id
        while category:
            if (category.name or '').strip().casefold() == 'raw materials':
                return True
            category = category.parent_id
        return False


class ProductCategoryType(models.Model):
    _name = 'product.category.type'
    _description = 'Type of Category'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Type', required=True, index=True)
    category_initial = fields.Integer(
        string='Category Initial',
        required=True,
        help='Numeric initial/code maintained on the category type.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    category_type_id = fields.Many2one(
        'product.category.type',
        string='Type',
        domain=[('active', '=', True)],
        ondelete='restrict',
        index=True,
        help=(
            'Type is available for categories whose Parent Category is '
            'Raw Materials. Category Initial is maintained on the Type.'
        ),
    )
    show_category_type = fields.Boolean(
        string='Show Category Type',
        compute='_compute_show_category_type',
    )
    # Legacy technical field kept for compatibility with any existing custom
    # code. It is no longer editable on Product Category; the value comes from
    # the selected Category Type.
    category_initial = fields.Integer(
        string='Category Initial',
        related='category_type_id.category_initial',
        store=True,
        readonly=True,
    )

    @api.depends('parent_id', 'parent_id.name')
    def _compute_show_category_type(self):
        for category in self:
            parent_name = (category.parent_id.name or '').strip().casefold()
            category.show_category_type = parent_name == 'raw materials'

    @api.onchange('parent_id')
    def _onchange_parent_id_requirement_category_type(self):
        for category in self:
            parent_name = (category.parent_id.name or '').strip().casefold()
            if parent_name != 'raw materials':
                category.category_type_id = False


class ProductProduct(models.Model):
    _inherit = 'product.product'

    thickness_microns = fields.Float(
        string='Thickness (Microns)',
        help=(
            'Optional variant-specific thickness used in CRM requirement form layers. '
            'If blank, the template thickness or the first number in the variant name is used.'
        ),
    )

    def _get_requirement_layer_thickness(self):
        self.ensure_one()
        if self.thickness_microns:
            return self.thickness_microns
        if self.product_tmpl_id.thickness_microns:
            return self.product_tmpl_id.thickness_microns

        text = self.display_name or self.name or ''
        match = re.search(r'(\d+(?:\.\d+)?)', text)
        if match:
            return float(match.group(1))
        return 0.0
