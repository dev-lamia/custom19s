from odoo import models, fields, api, _, tools


class SaleJobCodeRepeatSize(models.Model):
    _name = 'sale.job.code.repeat.size'
    _description = 'Job Code One Repeat Size'

    source_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        index=True,
        ondelete='cascade',
    )
    one_repeat_size = fields.Float(string='One Repeat Size')
    measuring_unit_id = fields.Many2one(
        'uom.uom',
        string='Measuring Unit',
        ondelete='set null',
    )

    _unique_source_line = models.Constraint(
        'UNIQUE(source_line_id)',
        'Only one One Repeat Size value is allowed per Job Code.',
    )


class SaleJobCodeConfiguration(models.Model):
    _name = 'sale.job.code.configuration'
    _description = 'Sale Job Code Configuration'
    _auto = False
    _order = 'id desc'
    _rec_name = 'job_code'
    _rec_names_search = ['job_code', 'gdn_number']

    job_code = fields.Char(string='Job Code', readonly=True, index=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        readonly=True,
    )
    order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True,
    )
    source_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True,
    )
    requirement_specification_id = fields.Many2one(
        'crm.requirement.specification',
        string='Requirement Specification',
        readonly=True,
    )
    requirement_form_id = fields.Many2one(
        'crm.requirement.form',
        string='REQ ID',
        readonly=True,
    )
    gdn_configuration_id = fields.Many2one(
        'sale.gdn.configuration',
        string='GDN Configuration',
        readonly=True,
    )
    gdn_number = fields.Char(string='GDN Number', readonly=True)

    design_name = fields.Char(string='Design Name', readonly=True)
    design_dimension_uom = fields.Selection(
        [
            ('mm', 'MM'),
            ('cm', 'CM'),
            ('inch', 'Inch'),
            ('meters', 'Meters'),
        ],
        string='Design Dimension UOM',
        readonly=True,
    )
    design_no = fields.Integer(string='No. Designs', readonly=True)
    color_reference = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Color Reference',
        readonly=True,
    )
    color_reference_type = fields.Selection(
        [('physical', 'Physical'), ('pantone', 'Pantone')],
        string='Color Reference Type',
        readonly=True,
    )
    quantity = fields.Integer(string='Quantity', readonly=True)
    quantity_uom_id = fields.Many2one(
        'uom.uom',
        string='Quantity UOM',
        readonly=True,
    )
    fg_type = fields.Selection(
        [('bag', 'Bag'), ('roll', 'Roll')],
        string='FG Type',
        readonly=True,
    )
    roll_type = fields.Selection(
        [('roll', 'Roll Stock'), ('label', 'Label')],
        string='Roll Type',
        readonly=True,
    )
    bag_type_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        readonly=True,
    )

    length = fields.Float(string='Length (mm)', readonly=True)
    width = fields.Integer(string='Width (mm)', readonly=True)
    gusset = fields.Float(string='Gusset (mm)', readonly=True)
    coil_width_mm = fields.Float(string='Coil Width (mm)', readonly=True)
    cutoff_length_mm = fields.Float(string='Cutoff Length (mm)', readonly=True)
    final_roll_direction = fields.Char(
        string='Final Roll Direction',
        readonly=True,
    )
    final_roll_weight_kg = fields.Float(
        string='Final Roll Weight (kg)',
        readonly=True,
    )
    final_roll_od_mm = fields.Float(string='Final Roll OD (mm)', readonly=True)
    final_roll_meters = fields.Float(string='Final Roll Meters', readonly=True)
    core_id_mm = fields.Float(string='Core ID (mm)', readonly=True)
    core_thickness_mm = fields.Float(
        string='Core Thickness (mm)',
        readonly=True,
    )
    core_type = fields.Char(string='Core Type', readonly=True)

    layer_1_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 1', readonly=True
    )
    layer_1_variant_id = fields.Many2one(
        'product.product', string='Layer 1 Thickness', readonly=True
    )
    layer_2_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 2', readonly=True
    )
    layer_2_variant_id = fields.Many2one(
        'product.product', string='Layer 2 Thickness', readonly=True
    )
    layer_3_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 3', readonly=True
    )
    layer_3_variant_id = fields.Many2one(
        'product.product', string='Layer 3 Thickness', readonly=True
    )
    layer_4_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 4', readonly=True
    )
    layer_4_variant_id = fields.Many2one(
        'product.product', string='Layer 4 Thickness', readonly=True
    )
    layer_5_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 5', readonly=True
    )
    layer_5_variant_id = fields.Many2one(
        'product.product', string='Layer 5 Thickness', readonly=True
    )
    layer_6_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 6', readonly=True
    )
    layer_6_variant_id = fields.Many2one(
        'product.product', string='Layer 6 Thickness', readonly=True
    )
    layer_7_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 7', readonly=True
    )
    layer_7_variant_id = fields.Many2one(
        'product.product', string='Layer 7 Thickness', readonly=True
    )
    layer_8_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 8', readonly=True
    )
    layer_8_variant_id = fields.Many2one(
        'product.product', string='Layer 8 Thickness', readonly=True
    )
    layer_9_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 9', readonly=True
    )
    layer_9_variant_id = fields.Many2one(
        'product.product', string='Layer 9 Thickness', readonly=True
    )
    layer_10_product_tmpl_id = fields.Many2one(
        'product.template', string='Layer 10', readonly=True
    )
    layer_10_variant_id = fields.Many2one(
        'product.product', string='Layer 10 Thickness', readonly=True
    )

    total_thickness = fields.Float(
        string='Total Thickness (Microns)',
        readonly=True,
    )
    print_finish_id = fields.Many2one(
        'crm.requirement.print.finish.option',
        string='Print and Finish',
        readonly=True,
    )
    additional_requirements = fields.Text(
        string='Additional Requirements',
        readonly=True,
    )

    # Live, read-only GDN design entries. Keep store=False because this model
    # is a SQL view and there are no corresponding SQL columns to fetch.
    gdn_color_details = fields.Integer(
        related='gdn_configuration_id.no_of_colors',
        string='Color Details',
        readonly=True,
        store=False,
    )
    gdn_print_type_id = fields.Many2one(
        'crm.requirement.print.type.option',
        related='gdn_configuration_id.print_type_id',
        string='Print Type',
        readonly=True,
        store=False,
    )

    # Independent Job Code-only uploads.  The SQL view is read-only storage,
    # so use the underlying Sale Order Line's dedicated attachment relation.
    job_quality_attachment_ids = fields.Many2many(
        'ir.attachment',
        related='source_line_id.job_quality_attachment_ids',
        string='Job Code Documents',
        readonly=False,
        store=False,
    )

    # Production parameters are linked to the originating Sale Order Line,
    # except One Repeat Size, which uses its own Job Code storage table.
    job_measuring_unit_id = fields.Many2one(
        'uom.uom',
        string='Measuring Unit',
    )
    job_process_sequence = fields.Many2many(
        'crm.job.production.process',
        'crm_job_process_sale_line_rel',
        'sale_line_id', 'process_id',
        string='Process Sequence',
    )
    job_one_up_size = fields.Char(string='One Up Size')
    job_one_repeat_size = fields.Float(string='One Repeat Size')
    job_number_of_ups = fields.Integer(string='No of Ups')
    job_number_of_repeats = fields.Integer(string='No of Repeats')
    job_circumference = fields.Float(string='Circumference')
    job_sleeve_size = fields.Char(string='Sleeve Size')
    job_print_area = fields.Float(string='Print Area')
    job_film_size_to_be_used = fields.Char(string='Film Size To Be Used')
    job_ink_gsm = fields.Float(string='Ink GSM', digits=(12, 3))
    job_adhesive_gsm = fields.Float(string='Adhesive GSM', digits=(12, 3))
    job_opv_gsm = fields.Float(string='OPV GSM', digits=(12, 3))
    job_total_gsm = fields.Float(string='Total GSM', digits=(12, 3))
    job_pouch_side_gusset = fields.Float(string='Side Gusset (mm)')
    job_pouch_bottom_gusset = fields.Float(string='Bottom Gusset (mm)')

    def write(self, vals):
        editable = {
            'job_process_sequence', 'job_one_up_size', 'job_one_repeat_size',
            'job_measuring_unit_id',
            'job_number_of_ups', 'job_number_of_repeats', 'job_circumference',
            'job_sleeve_size', 'job_print_area', 'job_film_size_to_be_used',
            'job_ink_gsm', 'job_adhesive_gsm', 'job_opv_gsm', 'job_total_gsm',
            'job_pouch_side_gusset', 'job_pouch_bottom_gusset',
            'job_quality_attachment_ids',
        }
        if set(vals) - editable:
            raise ValueError('Only manual production fields can be edited here.')

        # Job-specific measuring unit and repeat size persist in their
        # existing dedicated table; no new sale.order.line column is needed.
        storage_vals = {}
        if 'job_one_repeat_size' in vals:
            storage_vals['one_repeat_size'] = vals['job_one_repeat_size']
        if 'job_measuring_unit_id' in vals:
            storage_vals['measuring_unit_id'] = (
                vals['job_measuring_unit_id'] or False
            )
        if storage_vals:
            repeat_model = self.env['sale.job.code.repeat.size']
            existing = repeat_model.search([
                ('source_line_id', 'in', self.mapped('source_line_id').ids),
            ])
            existing_by_line = {
                item.source_line_id.id: item for item in existing
            }
            for record in self:
                line_id = record.source_line_id.id
                entry = existing_by_line.get(line_id)
                if entry:
                    entry.write(storage_vals)
                else:
                    existing_by_line[line_id] = repeat_model.create({
                        'source_line_id': line_id,
                        **storage_vals,
                    })

        line_vals = {
            name: value for name, value in vals.items()
            if name not in {
                'job_one_repeat_size', 'job_measuring_unit_id',
                'job_quality_attachment_ids',
            }
        }
        if line_vals:
            for record in self:
                record.source_line_id.write(line_vals)
        if 'job_quality_attachment_ids' in vals:
            # This folder belongs solely to the Job Code's source line.
            # Skip unrelated REQ/GDN field synchronization for file uploads.
            for record in self:
                record.source_line_id.with_context(
                    skip_sale_line_linked_sync=True,
                ).write({
                    'job_quality_attachment_ids': vals['job_quality_attachment_ids'],
                })
        return True

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE VIEW sale_job_code_configuration AS (
                SELECT
                    sol.id AS id,
                    sol.job_code AS job_code,
                    so.partner_id AS partner_id,
                    sol.order_id AS order_id,
                    sol.id AS source_line_id,
                    sol.product_id AS product_id,
                    sol.requirement_specification_id AS requirement_specification_id,
                    so.requirement_form_id AS requirement_form_id,
                    sol.gdn_configuration_id AS gdn_configuration_id,
                    sol.gdn_number AS gdn_number,
                    sol.req_design_name AS design_name,
                    sol.req_design_dimension_uom AS design_dimension_uom,
                    sol.req_design_no AS design_no,
                    sol.req_color_reference AS color_reference,
                    sol.req_color_reference_type AS color_reference_type,
                    sol.req_quantity AS quantity,
                    sol.req_quantity_uom_id AS quantity_uom_id,
                    sol.req_fg_type AS fg_type,
                    sol.req_roll_type AS roll_type,
                    sol.req_bag_type_product_tmpl_id AS bag_type_product_tmpl_id,
                    sol.req_length AS length,
                    sol.req_width AS width,
                    sol.req_gusset AS gusset,
                    sol.req_coil_width_mm AS coil_width_mm,
                    sol.req_cutoff_length_mm AS cutoff_length_mm,
                    sol.req_final_roll_direction AS final_roll_direction,
                    sol.req_final_roll_weight_kg AS final_roll_weight_kg,
                    sol.req_final_roll_od_mm AS final_roll_od_mm,
                    sol.req_final_roll_meters AS final_roll_meters,
                    sol.req_core_id_mm AS core_id_mm,
                    sol.req_core_thickness_mm AS core_thickness_mm,
                    sol.req_core_type AS core_type,
                    sol.req_layer_1_product_tmpl_id AS layer_1_product_tmpl_id,
                    sol.req_layer_1_variant_id AS layer_1_variant_id,
                    sol.req_layer_2_product_tmpl_id AS layer_2_product_tmpl_id,
                    sol.req_layer_2_variant_id AS layer_2_variant_id,
                    sol.req_layer_3_product_tmpl_id AS layer_3_product_tmpl_id,
                    sol.req_layer_3_variant_id AS layer_3_variant_id,
                    sol.req_layer_4_product_tmpl_id AS layer_4_product_tmpl_id,
                    sol.req_layer_4_variant_id AS layer_4_variant_id,
                    sol.req_layer_5_product_tmpl_id AS layer_5_product_tmpl_id,
                    sol.req_layer_5_variant_id AS layer_5_variant_id,
                    sol.req_layer_6_product_tmpl_id AS layer_6_product_tmpl_id,
                    sol.req_layer_6_variant_id AS layer_6_variant_id,
                    sol.req_layer_7_product_tmpl_id AS layer_7_product_tmpl_id,
                    sol.req_layer_7_variant_id AS layer_7_variant_id,
                    sol.req_layer_8_product_tmpl_id AS layer_8_product_tmpl_id,
                    sol.req_layer_8_variant_id AS layer_8_variant_id,
                    sol.req_layer_9_product_tmpl_id AS layer_9_product_tmpl_id,
                    sol.req_layer_9_variant_id AS layer_9_variant_id,
                    sol.req_layer_10_product_tmpl_id AS layer_10_product_tmpl_id,
                    sol.req_layer_10_variant_id AS layer_10_variant_id,
                    sol.req_total_thickness AS total_thickness,
                    sol.req_print_finish_id AS print_finish_id,
                    sol.req_additional_requirements AS additional_requirements,
                    sol.job_one_up_size AS job_one_up_size,
                    repeat_cfg.one_repeat_size AS job_one_repeat_size,
                    repeat_cfg.measuring_unit_id AS job_measuring_unit_id,
                    sol.job_number_of_ups AS job_number_of_ups,
                    sol.job_number_of_repeats AS job_number_of_repeats,
                    sol.job_circumference AS job_circumference,
                    sol.job_sleeve_size AS job_sleeve_size,
                    sol.job_print_area AS job_print_area,
                    sol.job_film_size_to_be_used AS job_film_size_to_be_used,
                    sol.job_ink_gsm AS job_ink_gsm,
                    sol.job_adhesive_gsm AS job_adhesive_gsm,
                    sol.job_opv_gsm AS job_opv_gsm,
                    sol.job_total_gsm AS job_total_gsm,
                    sol.job_pouch_side_gusset AS job_pouch_side_gusset,
                    sol.job_pouch_bottom_gusset AS job_pouch_bottom_gusset
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                LEFT JOIN sale_job_code_repeat_size repeat_cfg
                  ON repeat_cfg.source_line_id = sol.id
                WHERE sol.job_code IS NOT NULL
                  AND sol.job_code != ''
            )
            """
        )
