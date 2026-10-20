from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RequirementFgType(models.Model):
    _name = 'crm.requirement.fg.type'
    _description = 'Requirement FG Type'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='FG Type', required=True, translate=True)
    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help='Short unique code for the FG Type, for example BAG or ROLL.',
    )
    behavior = fields.Selection(
        [
            ('bag', 'Bag'),
            ('roll', 'Roll'),
        ],
        string='Specification Behavior',
        required=True,
        help=(
            'Controls which existing Product Specification layout and '
            'filtering rules this FG Type follows.'
        ),
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'crm_requirement_fg_type_code_unique',
            'unique(code)',
            'The FG Type code must be unique.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('code'):
                vals['code'] = vals['code'].strip().upper()
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('code'):
            vals['code'] = vals['code'].strip().upper()
        return super().write(vals)




class RequirementPrintFinishOption(models.Model):
    _name = 'crm.requirement.print.finish.option'
    _description = 'Requirement Print and Finish Option'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'crm_req_print_finish_code_unique',
            'unique(code)',
            'The print and finish option code must be unique.',
        ),
    ]


class RequirementPrintTypeOption(models.Model):
    _name = 'crm.requirement.print.type.option'
    _description = 'Requirement Print Type Option'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'crm_req_print_type_code_unique',
            'unique(code)',
            'The print type option code must be unique.',
        ),
    ]


class RequirementFeatureOption(models.Model):
    _name = 'crm.requirement.feature.option'
    _description = 'Requirement Feature Option'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'crm_req_feature_code_unique',
            'unique(code)',
            'The feature option code must be unique.',
        ),
    ]


class RequirementBagTypeOption(models.Model):
    _name = 'crm.requirement.bag.type.option'
    _description = 'Requirement Bag Type Option'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    hide_gusset = fields.Boolean(string='Hide Gusset')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        (
            'crm_req_bag_type_code_unique',
            'unique(code)',
            'The bag type option code must be unique.',
        ),
    ]


class ProductSpecification(models.Model):
    _name = 'crm.requirement.specification'
    _description = 'Product Specification Line'
    _order = 'sequence asc, id asc'

    form_id = fields.Many2one(
        'crm.requirement.form',
        string='Form',
        ondelete='cascade',
        required=True,
    )
    design_document_line_ids = fields.One2many(
        'crm.requirement.design.document.line',
        'specification_id',
        string='Design Documents',
        copy=True,
        help='Custom document types and multiple attachments per design.',
    )
    # Existing six-category attachments are retained for older records.
    # Files are stored per design, not per parent Requirement Form.
    doc_raw_file_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_raw_file_ids_rel',
        'specification_id', 'attachment_id',
        string='Raw File', copy=False,
    )
    doc_customer_approved_file_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_customer_approved_file_ids_rel',
        'specification_id', 'attachment_id',
        string='Customer Approved File', copy=False,
    )
    doc_production_layout_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_production_layout_ids_rel',
        'specification_id', 'attachment_id',
        string='Production Layout', copy=False,
    )
    doc_plate_layout_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_plate_layout_ids_rel',
        'specification_id', 'attachment_id',
        string='Plate Layout', copy=False,
    )
    doc_digital_print_file_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_digital_print_file_ids_rel',
        'specification_id', 'attachment_id',
        string='Digital Print File', copy=False,
    )
    doc_color_separation_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_spec_color_separation_ids_rel',
        'specification_id', 'attachment_id',
        string='Color Separation', copy=False,
    )

    def _sync_documents_to_linked_gdns(self):
        """Copy design attachments into the same categories on linked GDNs.

        Do not remove files already uploaded directly on the GDN.
        """
        document_fields = (
            'doc_raw_file_ids', 'doc_customer_approved_file_ids',
            'doc_production_layout_ids', 'doc_plate_layout_ids',
            'doc_digital_print_file_ids', 'doc_color_separation_ids',
        )
        for specification in self:
            configurations = specification.sale_order_line_ids.mapped(
                'gdn_configuration_id'
            )
            if not configurations:
                continue
            for configuration in configurations:
                updates = {}
                for field_name in document_fields:
                    ids = specification[field_name].ids
                    missing = set(ids) - set(configuration[field_name].ids)
                    if missing:
                        updates[field_name] = [(4, attachment_id) for attachment_id in sorted(missing)]
                if updates:
                    configuration.write(updates)
                configuration._sync_document_lines()

    is_repeat_job = fields.Boolean(
        string='Repeat Job',
        related='form_id.repeat_job',
        readonly=True,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Lead',
        related='form_id.lead_id',
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=1)
    is_duplicate_copy = fields.Boolean(
        string='Duplicated Specification',
        default=False,
        copy=False,
        help='Marks specifications created from the Duplicate button.',
    )
    layer_visible_count = fields.Integer(
        string='Visible Layer Count',
        default=1,
        copy=True,
        help='Controls how many layer rows are visible in the Product Specification form.',
    )

    previous_req_form = fields.Char(
        string='Previous Req Form',
        help=(
            'Previous requirement REQ ID. On the website it can be selected '
            'from prior submitted requirements or pasted manually.'
        ),
    )
    design_name = fields.Char(string='Design Name')
    design_dimension_uom = fields.Selection(
        [
            ('mm', 'MM'),
            ('cm', 'CM'),
            ('inch', 'Inch'),
            ('meters', 'Meters'),
        ],
        string='Design Dimension UOM',
        default='mm',
    )
    no_designs = fields.Integer(string='No. Designs', default=1)
    color_reference = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Color Reference')
    color_reference_type = fields.Selection([
        ('physical', 'Physical'),
        ('pantone', 'Pantone'),
    ], string='Color Reference Type')
    print_type_id = fields.Many2one(
        'crm.requirement.print.type.option',
        string='Print Type',
        ondelete='restrict',
    )
    no_of_colors = fields.Integer(string='No of Colors', default=0)
    quantity = fields.Integer(string='Quantity', default=0)
    # Legacy selection retained for backward compatibility with older records.
    quantity_uom = fields.Selection(
        [
            ('pcs', 'PCS'),
            ('kg', 'KG'),
            ('lm', 'LM'),
        ],
        string='Legacy Quantity UOM',
        default='pcs',
    )
    quantity_uom_id = fields.Many2one(
        'uom.uom',
        string='Quantity UOM',
        index=True,
        ondelete='restrict',
    )
    fg_type = fields.Selection(
        [
            ('bag', 'Bag'),
            ('roll', 'Roll'),
        ],
        string='FG Type',
        default='bag',
        required=True,
        index=True,
    )
    roll_type = fields.Selection(
        [
            ('roll', 'Roll Stock'),
            ('label', 'Label'),
        ],
        string='Roll Type',
        help='Shown only when FG Type is Roll. Both options use the same roll details.',
    )

    # Legacy Bag Type option retained only for backward compatibility.
    bag_type_id = fields.Many2one(
        'crm.requirement.bag.type.option',
        string='Legacy Bag Type',
        domain=[('active', '=', True)],
    )
    bag_type_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        index=True,
    )
    bag_type = fields.Char(
        string='Bag Type Text',
        help='Legacy code/text for older submitted records.',
    )
    bag_type_hide_gusset = fields.Boolean(
        string='Hide Gusset',
        compute='_compute_bag_type_hide_gusset',
        store=True,
    )

    length = fields.Float(string='Length (mm)')
    width = fields.Integer(string='Width (mm)')
    gusset = fields.Float(string='Gusset (mm)')

    coil_width_mm = fields.Float(string='Coil Width (mm)')
    cutoff_length_mm = fields.Float(string='Cutoff Length (mm)')
    final_roll_direction = fields.Char(string='Final Roll Direction')
    final_roll_weight_kg = fields.Float(string='Final Roll Weight (kg)')
    final_roll_od_mm = fields.Float(string='Final Roll OD (mm)')
    final_roll_meters = fields.Float(string='Final Roll Meters')
    core_id_mm = fields.Float(string='Core ID (mm)')
    core_thickness_mm = fields.Float(string='Core Thickness (mm)')
    core_type = fields.Char(string='Core Type')

    layer_1_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 1',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_1_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_1_material = fields.Char(string='Layer 1 Material')
    layer_1_thickness = fields.Float(string='Layer 1 Thickness (Microns)')

    layer_2_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 2',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_2_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_2_material = fields.Char(string='Layer 2 Material')
    layer_2_thickness = fields.Float(string='Layer 2 Thickness (Microns)')

    layer_3_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 3',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_3_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_3_material = fields.Char(string='Layer 3 Material')
    layer_3_thickness = fields.Float(string='Layer 3 Thickness (Microns)')

    layer_4_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 4',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_4_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_4_material = fields.Char(string='Layer 4 Material')
    layer_4_thickness = fields.Float(string='Layer 4 Thickness (Microns)')

    layer_5_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 5',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_5_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_5_material = fields.Char(string='Layer 5 Material')
    layer_5_thickness = fields.Float(string='Layer 5 Thickness (Microns)')

    layer_6_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 6',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_6_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_6_material = fields.Char(string='Layer 6 Material')
    layer_6_thickness = fields.Float(string='Layer 6 Thickness (Microns)')

    layer_7_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 7',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_7_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_7_material = fields.Char(string='Layer 7 Material')
    layer_7_thickness = fields.Float(string='Layer 7 Thickness (Microns)')

    layer_8_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 8',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_8_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_8_material = fields.Char(string='Layer 8 Material')
    layer_8_thickness = fields.Float(string='Layer 8 Thickness (Microns)')

    layer_9_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 9',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_9_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_9_material = fields.Char(string='Layer 9 Material')
    layer_9_thickness = fields.Float(string='Layer 9 Thickness (Microns)')

    layer_10_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Layer 10',
        domain=[
            ('active', '=', True),
            ('is_requirement_layer', '=', True),
        ],
    )
    layer_10_variant_id = fields.Many2one(
        'product.product', string='Thickness (Microns)'
    )
    layer_10_material = fields.Char(string='Layer 10 Material')
    layer_10_thickness = fields.Float(string='Layer 10 Thickness (Microns)')

    total_thickness = fields.Float(
        string='Total Thickness (Microns)',
        compute='_compute_total_thickness',
        store=True,
    )

    # Kept for backward compatibility with previous records/reports.
    material = fields.Char(string='Material')
    thickness = fields.Float(string='Legacy Thickness')
    weight = fields.Float(string='Weight (g)')

    print_finish_ids = fields.Many2many(
        'crm.requirement.print.finish.option',
        'crm_req_spec_print_finish_rel',
        'specification_id',
        'option_id',
        string='Print and Finish',
    )
    print_finish_id = fields.Many2one(
        'crm.requirement.print.finish.option',
        string='Print and Finish',
        compute='_compute_print_finish_id',
        inverse='_inverse_print_finish_id',
        store=True,
        readonly=False,
        domain=[('active', '=', True)],
    )
    standard_feature_ids = fields.Many2many(
        'crm.requirement.feature.option',
        'crm_req_spec_feature_rel',
        'specification_id',
        'option_id',
        string='Features',
    )

    # Legacy text fields kept so old submitted data remains visible.
    print_finish = fields.Char(
        string='Print and Finish Text',
        help='Legacy text generated from selected Print and Finish options.',
    )
    standard_features = fields.Char(
        string='Features Text',
        help='Legacy text generated from selected Feature options.',
    )

    valve = fields.Boolean(string='Valve')
    valve_type = fields.Selection([
        ('c', 'C Type'),
        ('s', 'S Type'),
    ], string='Valve Type')
    feature_tear_notch_zipper = fields.Boolean(string='Tear Notch')
    feature_rounded_corners = fields.Boolean(string='Rounded Corners')
    feature_other_note = fields.Text(string='Other Feature / Technical Note')
    forward_to_technical = fields.Boolean(
        string='Forward to Technical',
        compute='_compute_forward_to_technical',
        store=True,
    )
    back_if_yes = fields.Text(string='Back (If Valve Yes)')
    additional_requirements = fields.Text(string='Additional Requirements')
    customer_notes = fields.Text(
        string='Customer / Sales Design Note',
        help='Design-related note added by the Sales department for the designer.',
    )
    designer_note = fields.Text(
        string='Designer Note',
        help='Designer suggestion or internal note for other departments and future reference.',
    )
    summary_type = fields.Char(
        string='Type',
        compute='_compute_requirement_summary_fields',
        store=True,
    )
    summary_dimensions = fields.Char(
        string='Dimensions',
        compute='_compute_requirement_summary_fields',
        store=True,
    )
    summary_material_structure = fields.Char(
        string='Material / Structure',
        compute='_compute_requirement_summary_fields',
        store=True,
    )
    features = fields.Char(string='Features', compute='_compute_features')

    @api.depends(
        'fg_type',
        'roll_type',
        'bag_type_product_tmpl_id',
        'length',
        'width',
        'gusset',
        'coil_width_mm',
        'cutoff_length_mm',
        'layer_1_product_tmpl_id',
        'layer_1_variant_id',
        'layer_2_product_tmpl_id',
        'layer_2_variant_id',
        'layer_3_product_tmpl_id',
        'layer_3_variant_id',
        'layer_4_product_tmpl_id',
        'layer_4_variant_id',
        'layer_5_product_tmpl_id',
        'layer_5_variant_id',
        'layer_6_product_tmpl_id',
        'layer_6_variant_id',
        'layer_7_product_tmpl_id',
        'layer_7_variant_id',
        'layer_8_product_tmpl_id',
        'layer_8_variant_id',
        'layer_9_product_tmpl_id',
        'layer_9_variant_id',
        'layer_10_product_tmpl_id',
        'layer_10_variant_id',
    )
    def _compute_requirement_summary_fields(self):
        for rec in self:
            product_name = rec.bag_type_product_tmpl_id.display_name or ''
            if rec.fg_type == 'bag':
                rec.summary_type = (
                    f'Bag - {product_name}' if product_name else 'Bag'
                )
                dimensions = []
                if rec.length:
                    dimensions.append(f'L {rec.length:g} mm')
                if rec.width:
                    dimensions.append(f'W {rec.width:g} mm')
                if rec.gusset:
                    dimensions.append(f'G {rec.gusset:g} mm')
                rec.summary_dimensions = ' × '.join(dimensions)
            else:
                roll_label = 'Label' if rec.roll_type == 'label' else 'Roll Stock'
                rec.summary_type = (
                    f'{roll_label} - {product_name}' if product_name else roll_label
                )
                dimensions = []
                if rec.coil_width_mm:
                    dimensions.append(f'Coil {rec.coil_width_mm:g} mm')
                if rec.cutoff_length_mm:
                    dimensions.append(f'Cutoff {rec.cutoff_length_mm:g} mm')
                rec.summary_dimensions = ' × '.join(dimensions)

            layers = []
            for layer_no in range(1, 11):
                template = rec[f'layer_{layer_no}_product_tmpl_id']
                variant = rec[f'layer_{layer_no}_variant_id']
                if not template:
                    continue
                label = template.display_name
                layers.append(label)
            rec.summary_material_structure = ' / '.join(layers)

    source_specification_id = fields.Many2one(
        'crm.requirement.specification',
        string='Source Specification',
        copy=False,
        index=True,
        readonly=True,
        help=(
            'Original specification used when this design is copied as a '
            'Repeat Job.'
        ),
    )
    sale_order_line_ids = fields.One2many(
        'sale.order.line',
        'requirement_specification_id',
        string='Sale Order Lines',
        readonly=True,
    )
    job_code_link = fields.Html(
        string='Job Code',
        compute='_compute_sale_reference_links',
        readonly=True,
        sanitize=False,
    )
    gdn_number_link = fields.Html(
        string='GDN Number',
        compute='_compute_sale_reference_links',
        readonly=True,
        sanitize=False,
    )

    @api.depends(
        'sale_order_line_ids.job_code',
        'sale_order_line_ids.gdn_number',
        'sale_order_line_ids.gdn_configuration_id',
        'source_specification_id.sale_order_line_ids.gdn_number',
        'source_specification_id.sale_order_line_ids.gdn_configuration_id',
    )
    def _compute_sale_reference_links(self):
        """Show the Job/GDN created for this exact specification line.

        A Requirement Form design is linked to its Sale Order line through
        ``requirement_specification_id``.  Keeping the links on the design row
        makes it immediately clear which generated code belongs to which
        Product Specification.
        """
        for specification in self:
            job_links = []
            gdn_links = []
            seen_jobs = set()
            seen_gdns = set()

            lines = specification.sale_order_line_ids.filtered(
                lambda line: not line.display_type
            ).sorted(key=lambda line: (line.order_id.id, line.id))
            for line in lines:
                if line.job_code and line.job_code not in seen_jobs:
                    seen_jobs.add(line.job_code)
                    job_links.append(
                        Markup(
                            '<a href="/web#id={}&amp;model=sale.job.code.configuration'
                            '&amp;view_type=form">{}</a>'
                        ).format(line.id, escape(line.job_code))
                    )

            gdn_lines = lines
            if specification.source_specification_id:
                source_lines = (
                    specification.source_specification_id.sale_order_line_ids
                ).filtered(lambda line: not line.display_type)
                gdn_lines |= source_lines
            gdn_lines = gdn_lines.sorted(
                key=lambda line: (line.order_id.id, line.id)
            )
            for line in gdn_lines:
                configuration = line.gdn_configuration_id
                if (
                    line.gdn_number
                    and configuration
                    and configuration.id not in seen_gdns
                ):
                    seen_gdns.add(configuration.id)
                    gdn_links.append(
                        Markup(
                            '<a href="/web#id={}&amp;model=sale.gdn.configuration'
                            '&amp;view_type=form">{}</a>'
                        ).format(configuration.id, escape(line.gdn_number))
                    )

            separator = Markup('<br/>')
            specification.job_code_link = (
                separator.join(job_links) if job_links else False
            )
            specification.gdn_number_link = (
                separator.join(gdn_links) if gdn_links else False
            )

    def _spec_audit_excluded_fields(self):
        return {
            'id',
            'form_id',
            'create_uid',
            'create_date',
            'write_uid',
            'write_date',
            'sequence',
            'no_designs',
            'quantity_uom',
            'layer_visible_count',
            'bag_type_hide_gusset',
            'total_thickness',
            'sale_order_line_ids',
            'design_document_line_ids',
            'source_specification_id',
            'job_code_link',
            'gdn_number_link',
        }

    def _spec_audit_value(self, field_name):
        self.ensure_one()
        field = self._fields.get(field_name)
        if not field:
            return ''
        value = self[field_name]
        field_type = field.type
        if field_type == 'many2one':
            return value.display_name if value else ''
        if field_type in ('one2many', 'many2many'):
            return ', '.join(value.mapped('display_name')) if value else ''
        if field_type == 'selection':
            if not value:
                return ''
            try:
                return dict(field._description_selection(self.env)).get(
                    value, value
                )
            except Exception:
                return value
        if field_type == 'boolean':
            return _('Yes') if value else _('No')
        if field_type == 'binary':
            return _('Set') if value else _('Empty')
        if value in (False, None):
            return ''
        return str(value)

    def _spec_audit_title(self):
        self.ensure_one()
        design_no = self.no_designs or self.sequence or 1
        return _('Product Specification - Design %s') % design_no

    def _post_spec_audit(self, action, rows=None):
        rows = rows or []
        for rec in self:
            if not rec.form_id:
                continue
            title = '%s: %s' % (rec._spec_audit_title(), action)
            rec.form_id._post_requirement_audit(title, rows)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get('default_no_designs'):
            return values

        form_id = self.env.context.get('default_form_id')
        if not form_id or not isinstance(form_id, int):
            return values

        next_number = self.search_count([('form_id', '=', form_id)]) + 1
        if 'no_designs' in fields_list:
            values['no_designs'] = next_number
        if 'sequence' in fields_list:
            values['sequence'] = next_number
        return values

    def _resequence_form_lines(self, forms):
        """Keep design numbers consecutive and aligned with row order."""
        for form in forms.exists():
            lines = self.search(
                [('form_id', '=', form.id)],
                order='sequence asc, id asc',
            )
            for design_no, line in enumerate(lines, start=1):
                if (
                    line.sequence == design_no
                    and line.no_designs == design_no
                ):
                    continue
                line.with_context(
                    skip_requirement_audit=True,
                    skip_requirement_resequence=True,
                ).write({
                    'sequence': design_no,
                    'no_designs': design_no,
                })

    @api.model_create_multi
    def create(self, vals_list):
        # Repeat-job rows are first created as virtual One2many records by the
        # parent form onchange.  The web client may send only the fields that
        # were rendered/changed when the parent Requirement Form is saved.
        # Rehydrate every such row from its exact source specification before
        # create, then overlay the client values (notably QTY/UOM).  This keeps
        # the fetched design, dimensions, layers/materials, finish, features,
        # etc. intact after Save without changing normal/new-job behaviour.
        hydrated_vals_list = []
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            source_id = vals.get('source_specification_id')
            if source_id:
                source = self.browse(source_id).exists()
                if source:
                    source_vals = source.copy_data(default={
                        'form_id': vals.get('form_id') or source.form_id.id,
                    })[0]
                    # The browser can submit empty values for readonly fields
                    # of an onchange-created repeat row.  Never let those
                    # placeholders overwrite the fetched source design.  A
                    # repeat/duplicate copy may only change QTY and UOM; keep
                    # technical linkage/order values from the current form.
                    for field_name in ('id', 'sequence', 'no_designs'):
                        source_vals.pop(field_name, None)
                    allowed_from_client = {
                        'form_id', 'quantity', 'quantity_uom',
                        'quantity_uom_id', 'source_specification_id',
                        'previous_req_form', 'is_duplicate_copy',
                    }
                    for field_name in allowed_from_client:
                        if field_name in vals:
                            source_vals[field_name] = vals[field_name]
                    source_vals['source_specification_id'] = source.id
                    source_vals['is_duplicate_copy'] = True
                    vals = source_vals
            hydrated_vals_list.append(vals)
        vals_list = hydrated_vals_list

        self._prepare_bag_type_values(vals_list)
        for vals in vals_list:
            populated_layers = [
                layer_no
                for layer_no in range(2, 11)
                if vals.get(f'layer_{layer_no}_product_tmpl_id')
            ]
            minimum_visible = max(populated_layers, default=1)
            vals['layer_visible_count'] = max(
                int(vals.get('layer_visible_count') or 1),
                minimum_visible,
            )

        form_ids = {vals.get('form_id') for vals in vals_list if vals.get('form_id')}
        next_number_by_form = {form_id: 1 for form_id in form_ids}
        if form_ids:
            existing_lines = self.search([
                ('form_id', 'in', list(form_ids)),
            ])
            for line in existing_lines:
                next_number_by_form[line.form_id.id] = max(
                    next_number_by_form[line.form_id.id],
                    (line.no_designs or line.sequence or 0) + 1,
                )

        for vals in vals_list:
            form_id = vals.get('form_id')
            if not form_id:
                continue
            design_no = next_number_by_form[form_id]
            vals['sequence'] = design_no
            vals['no_designs'] = design_no
            next_number_by_form[form_id] += 1

        records = super().create(vals_list)
        records.with_context(skip_requirement_audit=True)._sync_multi_select_text()

        leads = records.mapped('form_id.lead_id')
        if leads:
            leads._refresh_requirement_summary()

        if not self.env.context.get('skip_requirement_resequence'):
            self._resequence_form_lines(records.mapped('form_id'))

        if not self.env.context.get('skip_requirement_audit'):
            excluded = records._spec_audit_excluded_fields()
            for rec in records:
                rows = []
                # Log populated business values on creation. Empty/default
                # fields are omitted so the chatter remains readable.
                for field_name, field in rec._fields.items():
                    if field_name in excluded or field.compute:
                        continue
                    if field_name in {'sequence', 'no_designs'}:
                        continue
                    value = rec._spec_audit_value(field_name)
                    if value in ('', 'No', '0', '0.0'):
                        continue
                    rows.append((field.string or field_name, '', value))
                rec._post_spec_audit(_('created'), rows)
        return records

    def write(self, vals):
        vals = dict(vals)
        skip_audit = self.env.context.get('skip_requirement_audit')
        original_fields = set(vals)

        if 'roll_type' in vals and 'fg_type' not in vals and self:
            if all(record.fg_type == 'roll' for record in self):
                vals['fg_type'] = 'roll'
        self._prepare_bag_type_values([vals])
        populated_layers = [
            layer_no
            for layer_no in range(2, 11)
            if vals.get(f'layer_{layer_no}_product_tmpl_id')
        ]
        if populated_layers:
            vals['layer_visible_count'] = max(
                int(vals.get('layer_visible_count') or 1),
                max(populated_layers),
            )

        excluded = self._spec_audit_excluded_fields()
        audit_fields = [
            field_name
            for field_name in vals
            if field_name in self._fields and field_name not in excluded
        ]
        before_by_record = {}
        if not skip_audit:
            before_by_record = {
                rec.id: {
                    field_name: rec._spec_audit_value(field_name)
                    for field_name in audit_fields
                }
                for rec in self
            }

        res = super().write(vals)
        if any(field_name in original_fields for field_name in (
            'doc_raw_file_ids', 'doc_customer_approved_file_ids',
            'doc_production_layout_ids', 'doc_plate_layout_ids',
            'doc_digital_print_file_ids', 'doc_color_separation_ids',
        )):
            self._sync_documents_to_linked_gdns()
        if not self.env.context.get('skip_requirement_multi_sync') and (
            'print_finish_ids' in original_fields
            or 'standard_feature_ids' in original_fields
        ):
            self.with_context(skip_requirement_audit=True)._sync_multi_select_text()

        leads = self.mapped('form_id.lead_id')
        if leads:
            leads._refresh_requirement_summary()

        if not skip_audit:
            for rec in self:
                rows = []
                before_values = before_by_record.get(rec.id, {})
                for field_name in audit_fields:
                    before = before_values.get(field_name, '')
                    after = rec._spec_audit_value(field_name)
                    if before == after:
                        continue
                    field = rec._fields[field_name]
                    rows.append((field.string or field_name, before, after))
                if rows:
                    rec._post_spec_audit(_('updated'), rows)
        return res

    def unlink(self):
        forms = self.mapped('form_id')
        audit_entries = []
        if not self.env.context.get('skip_requirement_audit'):
            for rec in self:
                if rec.form_id:
                    audit_entries.append((
                        rec.form_id,
                        rec._spec_audit_title(),
                        rec.design_name or '',
                    ))
        leads = forms.mapped('lead_id')
        result = super().unlink()

        if leads:
            leads._refresh_requirement_summary()

        if not self.env.context.get('skip_requirement_resequence'):
            self._resequence_form_lines(forms)

        for form, title, design_name in audit_entries:
            label = title
            if design_name:
                label = '%s (%s)' % (title, design_name)
            form._post_requirement_audit(
                _('%s: deleted') % label
            )
        return result

    @api.constrains('fg_type', 'bag_type_product_tmpl_id')
    def _check_fg_product_matches_type(self):
        for rec in self:
            product_tmpl = rec.bag_type_product_tmpl_id
            if (
                product_tmpl
                and rec.fg_type
                and product_tmpl.requirement_fg_type != rec.fg_type
            ):
                raise ValidationError(
                    _(
                        'Selected Product must match the selected FG Type.'
                    )
                )

    @api.constrains(
        'layer_1_product_tmpl_id',
        'layer_2_product_tmpl_id',
        'layer_3_product_tmpl_id',
        'layer_4_product_tmpl_id',
        'layer_5_product_tmpl_id',
        'layer_6_product_tmpl_id',
        'layer_7_product_tmpl_id',
        'layer_8_product_tmpl_id',
        'layer_9_product_tmpl_id',
        'layer_10_product_tmpl_id',
    )
    def _check_layer_products_are_allowed(self):
        for rec in self:
            for layer_no in range(1, 11):
                product_tmpl = rec[f'layer_{layer_no}_product_tmpl_id']
                if product_tmpl and not product_tmpl.is_requirement_layer:
                    raise ValidationError(
                        _(
                            'Product "%s" is not enabled as a Layer product.'
                        ) % product_tmpl.display_name
                    )

    def _prepare_bag_type_values(self, vals_list):
        """Normalize the selected FG product while keeping legacy fields usable."""
        ProductTemplate = self.env['product.template']
        BagType = self.env['crm.requirement.bag.type.option']
        hide_legacy_codes = {'three_side', 'two_side', 'label', 'roll_stock'}

        for vals in vals_list:
            selected_product = ProductTemplate.browse()
            selected_option = BagType.browse()
            fg_type = vals.get('fg_type')

            if 'bag_type_product_tmpl_id' in vals:
                selected_product = ProductTemplate.browse(
                    vals['bag_type_product_tmpl_id']
                ).exists()
                vals['bag_type'] = selected_product.display_name or False

                if selected_product:
                    selected_fg_type = selected_product.requirement_fg_type
                    if selected_fg_type and not fg_type:
                        fg_type = selected_fg_type
                        vals['fg_type'] = selected_fg_type

                    if selected_fg_type == 'roll':
                        code = (
                            selected_product.requirement_bag_type_code or ''
                        ).strip().upper()
                        vals['roll_type'] = (
                            'label' if code == 'LBL' else 'roll'
                        )
                    elif selected_fg_type == 'bag':
                        vals['roll_type'] = False
            elif 'bag_type_id' in vals:
                selected_option = BagType.browse(vals['bag_type_id']).exists()
                vals['bag_type'] = (
                    selected_option.code or selected_option.name or False
                )
            elif vals.get('bag_type') and not vals.get('bag_type_product_tmpl_id'):
                selected_product = ProductTemplate.search(
                    [('name', '=', vals['bag_type'])],
                    limit=1,
                )
                if selected_product and selected_product.requirement_fg_type:
                    vals['bag_type_product_tmpl_id'] = selected_product.id
                    if not fg_type:
                        vals['fg_type'] = selected_product.requirement_fg_type

            if fg_type == 'bag':
                vals['roll_type'] = False

            should_hide = False
            if selected_product:
                should_hide = selected_product.requirement_hide_gusset
            elif selected_option:
                should_hide = (
                    selected_option.hide_gusset
                    or selected_option.code in hide_legacy_codes
                )
            elif vals.get('bag_type') in hide_legacy_codes:
                should_hide = True

            if should_hide or fg_type == 'roll':
                vals['gusset'] = 0.0

    def _get_bag_type_display(self):
        self.ensure_one()
        if self.bag_type_product_tmpl_id:
            return self.bag_type_product_tmpl_id.display_name
        if self.bag_type_id:
            return self.bag_type_id.name
        legacy_map = {
            'stand': 'Stand Up Pouch',
            'flat': 'Flat Bottom Pouch',
            'quad_seal': 'Quad Seal Pouch',
            'three_side': '3 Side Seal Pouch',
            'two_side': '2 Side Seal Pouch',
            'label': 'Label',
            'roll_stock': 'Roll Stock',
        }
        return legacy_map.get(self.bag_type or '', self.bag_type or '')

    @api.depends(
        'bag_type_product_tmpl_id',
        'bag_type_product_tmpl_id.requirement_bag_type_code',
        'bag_type_id',
        'bag_type_id.hide_gusset',
        'bag_type',
        'fg_type',
    )
    def _compute_bag_type_hide_gusset(self):
        hide_codes = {'three_side', 'two_side', 'label', 'roll_stock'}
        for rec in self:
            product_hides_gusset = bool(
                rec.bag_type_product_tmpl_id
                and rec.bag_type_product_tmpl_id._requirement_should_hide_gusset()
            )
            rec.bag_type_hide_gusset = bool(
                rec.fg_type == 'roll'
                or product_hides_gusset
                or rec.bag_type_id.hide_gusset
                or rec.bag_type in hide_codes
            )

    @api.onchange('fg_type')
    def _onchange_fg_type(self):
        for rec in self:
            product_tmpl = rec.bag_type_product_tmpl_id
            if (
                product_tmpl
                and product_tmpl.requirement_fg_type != rec.fg_type
            ):
                rec.bag_type_product_tmpl_id = False
                rec.bag_type = False
                product_tmpl = self.env['product.template']

            if rec.fg_type == 'roll':
                rec.gusset = 0.0
                if product_tmpl:
                    code = (
                        product_tmpl.requirement_bag_type_code or ''
                    ).strip().upper()
                    rec.roll_type = 'label' if code == 'LBL' else 'roll'
                else:
                    rec.roll_type = False
            else:
                rec.roll_type = False

    @api.onchange('bag_type_product_tmpl_id')
    def _onchange_bag_type_product_tmpl_id_gusset(self):
        for rec in self:
            if (
                rec.bag_type_product_tmpl_id
                and rec.bag_type_product_tmpl_id._requirement_should_hide_gusset()
            ):
                rec.gusset = 0.0


    @api.depends('print_finish_ids')
    def _compute_print_finish_id(self):
        for rec in self:
            rec.print_finish_id = rec.print_finish_ids[:1]

    def _inverse_print_finish_id(self):
        for rec in self:
            rec.print_finish_ids = [(6, 0, rec.print_finish_id.ids)]
            rec.print_finish = rec.print_finish_id.name or False

    def _sync_multi_select_text(self):
        for rec in self:
            updates = {}
            print_finish = ', '.join(rec.print_finish_ids.mapped('name'))
            standard_features = ', '.join(rec.standard_feature_ids.mapped('name'))
            if print_finish and rec.print_finish != print_finish:
                updates['print_finish'] = print_finish
            if standard_features and rec.standard_features != standard_features:
                updates['standard_features'] = standard_features
            if rec.standard_feature_ids:
                codes = set(rec.standard_feature_ids.mapped('code'))
                has_valve_c = 'valve_c_type' in codes
                has_valve_s = 'valve_s_type' in codes
                updates.update({
                    'feature_tear_notch_zipper': 'tear_notch' in codes,
                    'feature_rounded_corners': bool(
                        {'rounded_corner_punch', 'rounded_corner_diecut'} & codes
                    ),
                    'valve': has_valve_c or has_valve_s,
                    'valve_type': 'c' if has_valve_c else ('s' if has_valve_s else False),
                })
            if updates:
                rec.with_context(
                    skip_requirement_multi_sync=True,
                    skip_requirement_audit=True,
                ).write(updates)

    def _set_layer_from_product(self, layer_no):
        self.ensure_one()
        product_tmpl = self[f'layer_{layer_no}_product_tmpl_id']
        variant = self[f'layer_{layer_no}_variant_id']

        # Opening or duplicating an existing design must not overwrite its
        # saved, possibly manually adjusted, layer thickness with the current
        # product default. Recalculate only when the selected product/variant
        # actually differs from the stored record.
        original = self._origin
        if original and original.id:
            old_tmpl = original[f'layer_{layer_no}_product_tmpl_id']
            old_variant = original[f'layer_{layer_no}_variant_id']
            if product_tmpl == old_tmpl and variant == old_variant:
                return

        if not product_tmpl:
            self[f'layer_{layer_no}_variant_id'] = False
            self[f'layer_{layer_no}_material'] = False
            self[f'layer_{layer_no}_thickness'] = 0.0
            return

        if variant and variant.product_tmpl_id != product_tmpl:
            variant = False
            self[f'layer_{layer_no}_variant_id'] = False

        if not variant and len(product_tmpl.product_variant_ids) == 1:
            variant = product_tmpl.product_variant_ids[:1]
            self[f'layer_{layer_no}_variant_id'] = variant.id

        self[f'layer_{layer_no}_material'] = product_tmpl.display_name or False
        self[f'layer_{layer_no}_thickness'] = (
            variant._get_requirement_layer_thickness()
            if variant
            else (product_tmpl.thickness_microns or 0.0)
        )

    @api.onchange('layer_1_product_tmpl_id', 'layer_1_variant_id')
    def _onchange_layer_1_product(self):
        for rec in self:
            rec._set_layer_from_product(1)

    @api.onchange('layer_2_product_tmpl_id', 'layer_2_variant_id')
    def _onchange_layer_2_product(self):
        for rec in self:
            rec._set_layer_from_product(2)

    @api.onchange('layer_3_product_tmpl_id', 'layer_3_variant_id')
    def _onchange_layer_3_product(self):
        for rec in self:
            rec._set_layer_from_product(3)

    @api.onchange('layer_4_product_tmpl_id', 'layer_4_variant_id')
    def _onchange_layer_4_product(self):
        for rec in self:
            rec._set_layer_from_product(4)

    @api.onchange('layer_5_product_tmpl_id', 'layer_5_variant_id')
    def _onchange_layer_5_product(self):
        for rec in self:
            rec._set_layer_from_product(5)

    @api.onchange('layer_6_product_tmpl_id', 'layer_6_variant_id')
    def _onchange_layer_6_product(self):
        for rec in self:
            rec._set_layer_from_product(6)

    @api.onchange('layer_7_product_tmpl_id', 'layer_7_variant_id')
    def _onchange_layer_7_product(self):
        for rec in self:
            rec._set_layer_from_product(7)

    @api.onchange('layer_8_product_tmpl_id', 'layer_8_variant_id')
    def _onchange_layer_8_product(self):
        for rec in self:
            rec._set_layer_from_product(8)

    @api.onchange('layer_9_product_tmpl_id', 'layer_9_variant_id')
    def _onchange_layer_9_product(self):
        for rec in self:
            rec._set_layer_from_product(9)

    @api.onchange('layer_10_product_tmpl_id', 'layer_10_variant_id')
    def _onchange_layer_10_product(self):
        for rec in self:
            rec._set_layer_from_product(10)

    @api.onchange('bag_type_product_tmpl_id')
    def _onchange_bag_type_product_tmpl_id(self):
        for rec in self:
            product_tmpl = rec.bag_type_product_tmpl_id
            if not product_tmpl:
                rec.bag_type = False
                rec.roll_type = False
                continue

            rec.bag_type = product_tmpl.display_name
            if product_tmpl.requirement_fg_type:
                rec.fg_type = product_tmpl.requirement_fg_type
            if rec.fg_type == 'roll':
                code = (
                    product_tmpl.requirement_bag_type_code or ''
                ).strip().upper()
                rec.roll_type = 'label' if code == 'LBL' else 'roll'
                rec.gusset = 0.0
            else:
                rec.roll_type = False
                if product_tmpl.requirement_hide_gusset:
                    rec.gusset = 0.0

    @api.onchange('bag_type_id')
    def _onchange_bag_type_id(self):
        for rec in self:
            if rec.bag_type_id:
                rec.bag_type = rec.bag_type_id.code or rec.bag_type_id.name
            if rec.bag_type_id.hide_gusset:
                rec.gusset = 0.0

    @api.onchange('color_reference')
    def _onchange_color_reference(self):
        for rec in self:
            if rec.color_reference != 'yes':
                rec.color_reference_type = False

    @api.onchange('print_finish_id')
    def _onchange_print_finish_id(self):
        for rec in self:
            rec.print_finish = rec.print_finish_id.name or False

    @api.onchange('standard_feature_ids')
    def _onchange_standard_feature_ids(self):
        for rec in self:
            codes = set(rec.standard_feature_ids.mapped('code'))
            remove_codes = set()

            if 'normal_zipper' in codes and 'tear_zipper' in codes:
                remove_codes.add('tear_zipper')
                codes.discard('tear_zipper')

            if 'tear_zipper' in codes:
                remove_codes.update({'tear_notch', 'easy_tear_laser'})

            if remove_codes:
                rec.standard_feature_ids = rec.standard_feature_ids.filtered(
                    lambda option: option.code not in remove_codes
                )
                codes = set(rec.standard_feature_ids.mapped('code'))

            has_valve_c = 'valve_c_type' in codes
            has_valve_s = 'valve_s_type' in codes
            rec.valve = has_valve_c or has_valve_s
            rec.valve_type = 'c' if has_valve_c else ('s' if has_valve_s else False)
            rec.feature_tear_notch_zipper = 'tear_notch' in codes
            rec.feature_rounded_corners = bool(
                {'rounded_corner_punch', 'rounded_corner_diecut'} & codes
            )
            rec.standard_features = ', '.join(rec.standard_feature_ids.mapped('name'))

    @api.depends(
        'layer_1_thickness',
        'layer_2_thickness',
        'layer_3_thickness',
        'layer_4_thickness',
        'layer_5_thickness',
        'layer_6_thickness',
        'layer_7_thickness',
        'layer_8_thickness',
        'layer_9_thickness',
        'layer_10_thickness',
        'thickness',
    )
    def _compute_total_thickness(self):
        for rec in self:
            layer_total = sum(
                rec[f'layer_{layer_no}_thickness']
                for layer_no in range(1, 11)
            )
            rec.total_thickness = layer_total or rec.thickness

    @api.depends('standard_features', 'standard_feature_ids', 'feature_other_note')
    def _compute_forward_to_technical(self):
        for rec in self:
            features_text = ' '.join(filter(None, [
                rec.standard_features,
                ' '.join(rec.standard_feature_ids.mapped('name')),
            ])).lower()
            rec.forward_to_technical = bool(
                rec.feature_other_note or 'other' in features_text
            )

    @api.depends(
        'standard_features',
        'standard_feature_ids',
        'feature_tear_notch_zipper',
        'feature_rounded_corners',
        'valve',
        'valve_type',
        'feature_other_note',
    )
    def _compute_features(self):
        for rec in self:
            features = []
            if rec.standard_feature_ids:
                features.extend(rec.standard_feature_ids.mapped('name'))
            elif rec.standard_features:
                features.extend(
                    item.strip()
                    for item in rec.standard_features.split(',')
                    if item.strip()
                )
            if rec.feature_tear_notch_zipper and 'Tear Notch' not in features:
                features.append('Tear Notch')
            if rec.feature_rounded_corners and 'Rounded Corners' not in features:
                features.append('Rounded Corners')
            if rec.valve and not any('Valve' in item for item in features):
                features.append('Valve')
            if rec.valve_type:
                valve_label = dict(self._fields['valve_type'].selection).get(
                    rec.valve_type
                )
                if valve_label and valve_label not in features:
                    features.append(valve_label)
            if rec.feature_other_note:
                features.append('Other / Technical')
            rec.features = ', '.join(dict.fromkeys(filter(None, features)))

    def init(self):
        """Unlock earlier duplicates that live on New Job forms (fully editable now)."""
        super().init()
        self.env.cr.execute("SELECT to_regclass('crm_requirement_form')")
        if not self.env.cr.fetchone()[0]:
            return
        self.env.cr.execute("""
            UPDATE crm_requirement_specification spec
               SET is_duplicate_copy = FALSE
              FROM crm_requirement_form form
             WHERE spec.form_id = form.id
               AND spec.is_duplicate_copy IS TRUE
               AND spec.source_specification_id IS NULL
               AND COALESCE(form.repeat_job, FALSE) = FALSE
        """)

    def action_duplicate_specification(self):
        """Duplicate the complete design as a new line on the same REQ form.

        New Job    -> the copy is a normal line: every field stays editable.
        Repeat Job -> the copy is a locked reference design: only QTY and UOM
                      can be edited (is_duplicate_copy drives the read-only
                      state of every other field in the view).
        """
        self.ensure_one()
        siblings = self.form_id.specification_ids
        next_number = max(siblings.mapped('no_designs') or [0]) + 1
        next_sequence = max(siblings.mapped('sequence') or [0]) + 1

        restricted = bool(
            self.form_id.repeat_job
            and (self.is_duplicate_copy or self.source_specification_id)
        )
        # Copy the persisted thickness snapshots explicitly. The layer
        # material/variant selection may trigger onchange on the client; the
        # snapshot values must not be recomputed or cleared on duplication.
        layer_snapshots = {
            f'layer_{layer_no}_thickness': self[f'layer_{layer_no}_thickness']
            for layer_no in range(1, 11)
        }
        self.copy({
            **layer_snapshots,
            'form_id': self.form_id.id,
            'no_designs': next_number,
            'sequence': next_sequence,
            # A locked Repeat Job copy keeps the original source so its
            # fetched GDN remains available after save.  A New Job copy must
            # not carry a source, otherwise create() would re-hydrate it from
            # that source and overwrite the user's edits.
            'source_specification_id': (
                self.source_specification_id.id if restricted else False
            ) or False,
            'previous_req_form': (
                self.previous_req_form if restricted else False
            ) or False,
            'is_duplicate_copy': restricted,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

