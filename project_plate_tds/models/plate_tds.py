from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup, escape
import re

class PlateTds(models.Model):
    _name = 'plate.tds'
    _description = 'Plate Technical Data Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Document Number', required=True, copy=False, default='New', readonly=True)
    date = fields.Datetime(string='Generated On', default=fields.Datetime.now, required=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')], default='draft', tracking=True)
    task_id = fields.Many2one('project.task', string='Artwork Task', required=True, index=True, ondelete='cascade')
    gdn_id = fields.Many2one('sale.gdn.configuration', string='GDN', required=True, index=True, ondelete='restrict')
    sale_line_id = fields.Many2one('sale.order.line', string='Sales Order Line', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True, tracking=True)
    supplier_id = fields.Many2one('res.partner', string='Supplier', tracking=True)
    supplier_code = fields.Char(string='Supplier Code', tracking=True)
    supplier_name = fields.Char(string='Supplier Name', tracking=True)
    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True, tracking=True)
    customer_code = fields.Char(string='Customer Code', readonly=True, tracking=True)
    pr_rfq = fields.Char(string='PR No. / RFQ', tracking=True)
    job_code = fields.Char(string='Job Code', readonly=True)

    job_code_id = fields.Many2one(
        'sale.job.code.configuration',
        string='Job Code',
        compute='_compute_job_code_id',
        readonly=True,
    )

    @api.depends('sale_line_id')
    def _compute_job_code_id(self):
        lines = self.mapped('sale_line_id')
        jobs = self.env['sale.job.code.configuration'].search([
            ('source_line_id', 'in', lines.ids)
        ])
        job_map = {job.source_line_id.id: job.id for job in jobs}
        for rec in self:
            rec.job_code_id = job_map.get(rec.sale_line_id.id, False)

    design_name = fields.Char(string='Job Description / Design Name', readonly=True)
    structure = fields.Char(string='Structure', compute='_compute_gdn_details', readonly=True)
    fg_type = fields.Char(string='FG Type', compute='_compute_gdn_details', readonly=True)
    fg_type_key = fields.Selection(related='gdn_id.fg_type', string='FG Type Key', readonly=True)
    so_no = fields.Char(string='S.O. No.', readonly=True)
    gdn_number = fields.Char(string='GDN Number', readonly=True)
    design_type = fields.Selection([('new', 'New'), ('repeat', 'Repeat')], string='Type of Design', default='new')
    fg_width = fields.Float(string='Width of FG (mm)', digits=(16, 2), readonly=True)
    fg_length = fields.Float(string='Length of FG (mm)', digits=(16, 2), readonly=True)

    side_gusset = fields.Float(
        string='Side Gusset (mm)',
        digits=(16, 2),
        compute='_compute_job_gussets',
        readonly=True,
    )
    bottom_gusset = fields.Float(
        string='Bottom Gusset (mm)',
        digits=(16, 2),
        compute='_compute_job_gussets',
        readonly=True,
    )

    @api.depends(
        'job_code_id',
        'job_code_id.job_pouch_side_gusset',
        'job_code_id.job_pouch_bottom_gusset',
    )
    def _compute_job_gussets(self):
        for rec in self:
            job = rec.job_code_id
            rec.side_gusset = job.job_pouch_side_gusset or 0.0 if job else 0.0
            rec.bottom_gusset = job.job_pouch_bottom_gusset or 0.0 if job else 0.0

    print_type = fields.Char(
        string='Print Type',
        related='gdn_id.print_type_id.name',
        readonly=True,
    )
    pouch_type = fields.Char(string='Product', compute='_compute_gdn_details', readonly=True)
    plate_thickness = fields.Float(string='Plate Thickness (mm)', digits=(16, 3), tracking=True)
    one_up_width = fields.Float(
        string='One Up Width (mm)', digits=(16, 2),
        compute='_compute_job_dimensions', readonly=True,
    )
    width_bleed = fields.Float(string='Bleed for Width (mm)', digits=(16, 2), tracking=True)

    num_colors = fields.Integer(
        string='No. of Colors',
        compute='_compute_gdn_colors',
        readonly=True,
    )
    num_ups = fields.Integer(
        string='No. of Ups',
        compute='_compute_job_counts',
        readonly=True,
    )
    num_repeats = fields.Integer(
        string='No. of Repeats',
        compute='_compute_job_counts',
        readonly=True,
    )

    @api.depends('gdn_id')
    def _compute_gdn_colors(self):
        for rec in self:
            gdn = rec.gdn_id
            rec.num_colors = (
                gdn.no_of_colors or 0
                if gdn and 'no_of_colors' in gdn._fields else 0
            )

    @api.depends(
        'sale_line_id',
        'sale_line_id.job_number_of_ups',
        'sale_line_id.job_number_of_repeats',
    )
    def _compute_job_counts(self):
        for rec in self:
            line = rec.sale_line_id or rec.gdn_id.source_line_id
            rec.num_ups = line.job_number_of_ups if line else 0
            rec.num_repeats = line.job_number_of_repeats if line else 0


    print_area_width = fields.Float(
        string='Print Area Width (mm)',
        compute='_compute_print_area_width',
        readonly=True,
    )
    @api.depends('sale_line_id', 'sale_line_id.job_print_area')
    def _compute_print_area_width(self):
        for rec in self:
            line = rec.sale_line_id or rec.gdn_id.source_line_id
            rec.print_area_width = line.job_print_area if line else 0.0

    film_width = fields.Float(string='Film Width (mm)', digits=(16, 2), tracking=True)
    one_repeat_length = fields.Float(
        string='One Repeat Length (mm)',
        digits=(16, 2),
        compute='_compute_one_repeat_length',
        readonly=True,
    )

    @api.depends('sale_line_id', 'gdn_id.source_line_id')
    def _compute_one_repeat_length(self):
        jobs = self.env['sale.job.code.configuration']
        source_lines = self.mapped('sale_line_id') | self.mapped('gdn_id.source_line_id')
        job_records = jobs.search([('source_line_id', 'in', source_lines.ids)])
        job_by_line = {job.source_line_id.id: job for job in job_records}
        for rec in self:
            line = rec.sale_line_id or rec.gdn_id.source_line_id
            job = job_by_line.get(line.id) if line else False
            rec.one_repeat_length = (
                job.job_one_repeat_size or 0.0
                if job and 'job_one_repeat_size' in job._fields else 0.0
            )


    repeat_bleed = fields.Float(string='Bleed for Repeat (mm)', digits=(16, 2), tracking=True)

    circumference = fields.Float(
        string='Circumference (mm)', digits=(16, 2),
        compute='_compute_job_dimensions', readonly=True,
    )
    available_sleeve = fields.Float(
        string='Available Sleeve (mm)', digits=(16, 2),
        compute='_compute_job_dimensions', readonly=True,
    )
    

    @api.depends(
        'sale_line_id',
        'sale_line_id.job_one_up_size',
        'sale_line_id.job_circumference',
        'sale_line_id.job_sleeve_size',
        'gdn_id.source_line_id',
    )
    def _compute_job_dimensions(self):
        for rec in self:
            line = rec.sale_line_id or rec.gdn_id.source_line_id

            rec.one_up_width = (
                rec._job_mm_value(line.job_one_up_size) if line else 0.0
            )
            rec.circumference = line.job_circumference or 0.0 if line else 0.0
            rec.available_sleeve = (
                rec._job_mm_value(line.job_sleeve_size) if line else 0.0
            )


    num_plates = fields.Integer(string='No. of Plates' , tracking=True)
    print_direction = fields.Char(
        string='Print Direction',
        related='gdn_id.print_direction',
        readonly=True,
    )
    final_direction = fields.Char(string='Final Direction', compute='_compute_gdn_details', readonly=True, tracking=True)
    shade_reference = fields.Char(string='Color Reference', compute='_compute_gdn_details', readonly=True, tracking=True)
    staggering = fields.Boolean(string='Staggering', tracking=True)
    staggering_displacement = fields.Float(string='Staggering Displacement (mm)', digits=(16, 2), tracking=True)
    ink_grade = fields.Char(string='Ink Grade', tracking=True)
    plate_line_ids = fields.One2many('plate.tds.line', 'tds_id', string='Plate Codes', copy=True)
    production_layout_ids = fields.Many2many(
        'ir.attachment', 'plate_tds_prod_att_rel', 'tds_id', 'attachment_id', string='Production Layout')
    plate_layout_ids = fields.Many2many(
        'ir.attachment', 'plate_tds_plate_att_rel', 'tds_id', 'attachment_id', string='Plate Layout')
    remarks = fields.Text(string='Remarks', tracking=True)



    @staticmethod
    def _job_mm_value(value):
        if value is None or value is False:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return 0.0

        match = re.fullmatch(
            r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:mm)?',
            text,
            flags=re.IGNORECASE,
        )
        return float(match.group(1)) if match else 0.0




    @api.depends(
        'gdn_id', 'gdn_id.fg_type', 'gdn_id.bag_type_product_tmpl_id',
        'gdn_id.color_reference', 'gdn_id.color_reference_type',
        'gdn_id.source_line_id.req_final_roll_direction',
        'gdn_id.layer_1_product_tmpl_id', 'gdn_id.layer_1_variant_id',
        'gdn_id.layer_2_product_tmpl_id', 'gdn_id.layer_2_variant_id',
        'gdn_id.layer_3_product_tmpl_id', 'gdn_id.layer_3_variant_id',
        'gdn_id.layer_4_product_tmpl_id', 'gdn_id.layer_4_variant_id',
        'gdn_id.layer_5_product_tmpl_id', 'gdn_id.layer_5_variant_id',
        'gdn_id.layer_6_product_tmpl_id', 'gdn_id.layer_6_variant_id',
        'gdn_id.layer_7_product_tmpl_id', 'gdn_id.layer_7_variant_id',
        'gdn_id.layer_8_product_tmpl_id', 'gdn_id.layer_8_variant_id',
        'gdn_id.layer_9_product_tmpl_id', 'gdn_id.layer_9_variant_id',
        'gdn_id.layer_10_product_tmpl_id', 'gdn_id.layer_10_variant_id',
    )
    def _compute_gdn_details(self):
        for rec in self:
            gdn = rec.gdn_id
            if not gdn:
                rec.structure = False
                rec.fg_type = False
                rec.pouch_type = False
                rec.shade_reference = False
                rec.final_direction = False
                continue
            layers = []
            for number in range(1, 11):
                product = gdn[f'layer_{number}_product_tmpl_id']
                variant = gdn[f'layer_{number}_variant_id']
                if product or variant:
                    layers.append((variant or product).display_name)
            rec.structure = ' / '.join(layers) or False
            rec.fg_type = dict(
                gdn._fields['fg_type']._description_selection(self.env)
            ).get(gdn.fg_type, '')
            rec.pouch_type = gdn.bag_type_product_tmpl_id.display_name or False
            reference = gdn.color_reference
            if reference == 'yes':
                types = dict(
                    gdn._fields['color_reference_type']._description_selection(self.env)
                )
                rec.shade_reference = types.get(gdn.color_reference_type, 'Yes')
            elif reference == 'no':
                rec.shade_reference = 'No'
            else:
                rec.shade_reference = False
            rec.final_direction = (
                gdn.source_line_id.req_final_roll_direction or False
                if gdn.fg_type == 'roll' else False
            )

    _task_one_tds = models.Constraint(
        'UNIQUE(task_id)',
        'A Plate TDS already exists for this Artwork Task.',
    )

    @api.model
    def _prepare_from_task(self, task):
        line = task.artwork_sale_order_line_id
        gdn = line.gdn_configuration_id
        if not gdn:
            raise UserError(_('The Artwork Task does not have a linked GDN.'))
        partner = gdn.partner_id
        return {
            'task_id': task.id,
            'gdn_id': gdn.id,
            'sale_line_id': line.id,
            'sale_order_id': line.order_id.id,
            'customer_id': partner.id,
            'customer_code': partner.customer_code or '',
            'job_code': line.job_code or '',
            'design_name': gdn.design_name or '',
            'so_no': line.order_id.name or '',
            'gdn_number': gdn.gdn_number or '',
            'fg_width': gdn.width or 0.0,
            'fg_length': gdn.length or 0.0,
            
            'production_layout_ids': [(6, 0, gdn.doc_production_layout_ids.ids)],
            'plate_layout_ids': [(6, 0, gdn.doc_plate_layout_ids.ids)],
        }

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            self.update(self._prepare_from_task(self.task_id))

    @api.onchange('supplier_id')
    def _onchange_supplier_id(self):
        if self.supplier_id:
            self.supplier_name = self.supplier_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('plate.tds') or 'New'
            if vals.get('task_id'):
                task = self.env['project.task'].browse(vals['task_id'])
                defaults = self._prepare_from_task(task)
                for key, value in defaults.items():
                    vals.setdefault(key, value)
        return super().create(vals_list)



    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_print_tds(self):
        self.ensure_one()
        return self.env.ref('project_plate_tds.action_report_plate_tds').report_action(self)


class PlateTdsLine(models.Model):
    _name = 'plate.tds.line'
    _description = 'Plate Technical Data Sheet Line'
    _order = 'sequence, id'

    tds_id = fields.Many2one('plate.tds', string='Plate TDS', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10 , tracking=True)
    
    plate_product_id = fields.Many2one(
        'product.product',
        string='Plate Code',
        domain="[('product_tmpl_id.is_plate', '=', True)]",
        ondelete='restrict',
    )

    description = fields.Char(string='Plate Description' , tracking=True)
    plate_sequence = fields.Integer(string='Plate Sequence' , tracking=True)
    remarks = fields.Char(string='Remarks', tracking=True)



    def write(self, vals):
        tracked_fields = {
            'plate_product_id', 'plate_code',
            'description', 'plate_sequence', 'remarks',
        }
        changed = tracked_fields.intersection(vals)

        old_values = {}
        if changed:
            for line in self:
                old_values[line.id] = {
                    name: line._fields[name].convert_to_display_name(
                        line[name], line
                    )
                    for name in changed
                }

        result = super().write(vals)

        if changed:
            for line in self:
                changes = []
                for name in sorted(changed):
                    field = line._fields[name]
                    old = old_values[line.id][name]
                    new = field.convert_to_display_name(line[name], line)
                    if old != new:
                        changes.append(
                            Markup('<strong>%s:</strong> %s → %s') % (
                                escape(field.string),
                                escape(old or '-'),
                                escape(new or '-'),
                            )
                        )

                if changes and line.tds_id:
                    line.tds_id.message_post(
                        body=Markup('<br/>').join(changes),
                        subtype_xmlid='mail.mt_note',
                    )

        return result
