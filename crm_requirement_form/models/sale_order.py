from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleGdnConfiguration(models.Model):
    _name = 'sale.gdn.configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Sale GDN Configuration'
    _order = 'id desc'
    _rec_name = 'gdn_number'
    _rec_names_search = ['gdn_number', 'design_name']

    # Odoo's standard active flag archives the record without deleting it.
    active = fields.Boolean(
        string='Active', default=True, readonly=True, tracking=True,
    )

    def action_open_disable_wizard(self):
        """Ask for an audit reason before archiving selected GDN records."""
        gdns = self.filtered('active')
        if not gdns:
            raise UserError(_('Please select at least one active GDN to disable.'))
        # Do not create the transient record before prompting for a reason:
        # its required `reason` field must be provided when the user confirms.
        # The selected GDNs are defaulted into the unsaved popup instead.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Disable GDN'),
            'res_model': 'sale.gdn.disable.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'crm_requirement_form.sale_gdn_disable_wizard_form_view'
            ).id,
            'target': 'new',
            'context': dict(
                self.env.context,
                default_gdn_ids=[(6, 0, gdns.ids)],
            ),
        }

    def _gdn_document_audit_snapshot(self):
        """Read GDN document labels and filenames for manual change logging."""
        return {
            record.id: {
                line.id: (
                    line.document_type_id.display_name or line.document_type,
                    tuple(sorted(line.attachment_ids.mapped('name'))),
                )
                for line in record.gdn_document_line_ids
            }
            for record in self
        }

    def write(self, vals):
        # Stored GDN manual fields use native mail.thread tracking=True.
        # Inline document file changes happen in the child records, so log
        # them only when the user saves document rows through this GDN form.
        log_documents = (
            'gdn_document_line_ids' in vals
            and not self.env.context.get('tracking_disable')
            and not self.env.context.get('mail_notrack')
        )
        old_documents = self._gdn_document_audit_snapshot() if log_documents else {}
        result = super().write(vals)
        if log_documents:
            from markupsafe import Markup, escape

            new_documents = self._gdn_document_audit_snapshot()
            for record in self:
                before = old_documents.get(record.id, {})
                after = new_documents.get(record.id, {})
                if before == after:
                    continue
                descriptions = []
                for line_id in sorted(set(before) | set(after)):
                    old = before.get(line_id)
                    new = after.get(line_id)
                    if old == new:
                        continue
                    label = (new or old)[0]
                    old_files = ', '.join(old[1]) if old else ''
                    new_files = ', '.join(new[1]) if new else ''
                    descriptions.append(
                        Markup('<li>%s: %s → %s</li>') % (
                            escape(label or 'Document'),
                            escape(old_files or '—'),
                            escape(new_files or '—'),
                        )
                    )
                if descriptions:
                    record.message_post(
                        body=Markup('<p>GDN Documents updated</p><ul>%s</ul>')
                        % Markup('').join(descriptions),
                        subtype_xmlid='mail.mt_note',
                    )
        return result

    gdn_number = fields.Char(
        string='GDN Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict',
        tracking=True,
    )
    fg_type = fields.Selection(
        [('bag', 'Bag'), ('roll', 'Roll')],
        string='FG Type',
        readonly=True,
        tracking=True,
    )
    roll_type = fields.Selection(
        [('roll', 'Roll Stock'), ('label', 'Label')],
        string='Roll Type',
        readonly=True,
        tracking=True,
    )
    bag_type_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        readonly=True,
        index=True,
        tracking=True,
    )
    source_order_id = fields.Many2one(
        'sale.order',
        string='Source Sale Order',
        readonly=True,
        ondelete='set null',
        tracking=True,
    )
    source_line_id = fields.Many2one(
        'sale.order.line',
        string='Source Sale Order Line',
        readonly=True,
        ondelete='set null',
    )
    requirement_form_id = fields.Many2one(
        'crm.requirement.form',
        string='REQ ID',
        related='source_order_id.requirement_form_id',
        readonly=True,
    )
    design_name = fields.Char(string='Design Name', readonly=True, tracking=True)
    design_dimension_uom = fields.Selection(
        [
            ('mm', 'MM'),
            ('cm', 'CM'),
            ('inch', 'Inch'),
            ('meters', 'Meters'),
        ],
        string='Design Dimension UOM',
        readonly=True,
        tracking=True,
    )
    quantity = fields.Integer(string='Quantity', readonly=True)
    quantity_uom = fields.Selection(
        [('pcs', 'PCS'), ('kg', 'KG'), ('lm', 'LM')],
        string='Legacy Quantity UOM',
        readonly=True,
    )
    quantity_uom_id = fields.Many2one(
        'uom.uom',
        string='Quantity UOM',
        readonly=True,
        ondelete='restrict',
    )
    length = fields.Float(string='Length (mm)', readonly=True)
    width = fields.Integer(string='Width (mm)', readonly=True)
    gusset = fields.Float(string='Gusset (mm)', readonly=True)
    total_thickness = fields.Float(
        string='Total Thickness (Microns)',
        readonly=True,
    )
    print_finish_id = fields.Many2one(
        'crm.requirement.print.finish.option',
        string='Print and Finish',
        readonly=True,
        tracking=True,
    )
    color_reference = fields.Selection(
        related='source_line_id.req_color_reference',
        string='Color Reference',
        readonly=True,
    )
    color_reference_type = fields.Selection(
        related='source_line_id.req_color_reference_type',
        string='Color Reference Type',
        readonly=True,
    )
    # GDN-only manual entries; do not write to the Requirement Form/Sale Order.
    print_type_id = fields.Many2one(
        'crm.requirement.print.type.option',
        string='Print Type',
        ondelete='restrict',
        tracking=True,
    )
    no_of_colors = fields.Integer(string='No of Colors', default=0, tracking=True)
    print_direction = fields.Char(string='Print Direction', tracking=True)
    # Roll dimensions are read directly from the originating Sale Order line,
    # preserving the Requirement Form -> Sale Order -> GDN value mapping.
    coil_width_mm = fields.Float(
        related='source_line_id.req_coil_width_mm',
        string='Coil Width (mm)',
        readonly=True,
    )
    cutoff_length_mm = fields.Float(
        related='source_line_id.req_cutoff_length_mm',
        string='Cutoff Length (mm)',
        readonly=True,
    )
    final_roll_direction = fields.Char(
        related='source_line_id.req_final_roll_direction',
        string='Final Roll Direction',
        readonly=True,
    )
    final_roll_weight_kg = fields.Float(
        related='source_line_id.req_final_roll_weight_kg',
        string='Final Roll Weight (kg)',
        readonly=True,
    )
    final_roll_od_mm = fields.Float(
        related='source_line_id.req_final_roll_od_mm',
        string='Final Roll OD (mm)',
        readonly=True,
    )
    final_roll_meters = fields.Float(
        related='source_line_id.req_final_roll_meters',
        string='Final Roll Meters',
        readonly=True,
    )
    core_id_mm = fields.Float(
        related='source_line_id.req_core_id_mm',
        string='Core ID (mm)',
        readonly=True,
    )
    core_thickness_mm = fields.Float(
        related='source_line_id.req_core_thickness_mm',
        string='Core Thickness (mm)',
        readonly=True,
    )
    core_type = fields.Char(
        related='source_line_id.req_core_type',
        string='Core Type',
        readonly=True,
    )
    feature_ids = fields.Many2many(
        related='source_line_id.req_feature_ids',
        string='Features',
        readonly=True,
    )
    customer_notes = fields.Text(
        related='source_line_id.requirement_specification_id.customer_notes',
        string='Customer / Sales Design Note',
        readonly=False,
        tracking=True,
    )
    designer_note = fields.Text(
        related='source_line_id.requirement_specification_id.designer_note',
        string='Designer Note',
        readonly=False,
        tracking=True,
    )
    weight = fields.Float(
        related='source_line_id.requirement_specification_id.weight',
        string='Weight (g)',
        readonly=True,
    )
    layer_1_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_1_product_tmpl_id',
        string='Layer 1',
        readonly=True,
    )
    layer_1_variant_id = fields.Many2one(
        related='source_line_id.req_layer_1_variant_id',
        string='Layer 1 Thickness',
        readonly=True,
    )
    layer_1_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_1_thickness',
        string='Layer 1 Thickness (Microns)',
        readonly=True,
    )
    layer_2_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_2_product_tmpl_id',
        string='Layer 2',
        readonly=True,
    )
    layer_2_variant_id = fields.Many2one(
        related='source_line_id.req_layer_2_variant_id',
        string='Layer 2 Thickness',
        readonly=True,
    )
    layer_2_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_2_thickness',
        string='Layer 2 Thickness (Microns)',
        readonly=True,
    )
    layer_3_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_3_product_tmpl_id',
        string='Layer 3',
        readonly=True,
    )
    layer_3_variant_id = fields.Many2one(
        related='source_line_id.req_layer_3_variant_id',
        string='Layer 3 Thickness',
        readonly=True,
    )
    layer_3_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_3_thickness',
        string='Layer 3 Thickness (Microns)',
        readonly=True,
    )
    layer_4_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_4_product_tmpl_id',
        string='Layer 4',
        readonly=True,
    )
    layer_4_variant_id = fields.Many2one(
        related='source_line_id.req_layer_4_variant_id',
        string='Layer 4 Thickness',
        readonly=True,
    )
    layer_4_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_4_thickness',
        string='Layer 4 Thickness (Microns)',
        readonly=True,
    )
    layer_5_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_5_product_tmpl_id',
        string='Layer 5',
        readonly=True,
    )
    layer_5_variant_id = fields.Many2one(
        related='source_line_id.req_layer_5_variant_id',
        string='Layer 5 Thickness',
        readonly=True,
    )
    layer_5_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_5_thickness',
        string='Layer 5 Thickness (Microns)',
        readonly=True,
    )
    layer_6_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_6_product_tmpl_id',
        string='Layer 6',
        readonly=True,
    )
    layer_6_variant_id = fields.Many2one(
        related='source_line_id.req_layer_6_variant_id',
        string='Layer 6 Thickness',
        readonly=True,
    )
    layer_6_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_6_thickness',
        string='Layer 6 Thickness (Microns)',
        readonly=True,
    )
    layer_7_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_7_product_tmpl_id',
        string='Layer 7',
        readonly=True,
    )
    layer_7_variant_id = fields.Many2one(
        related='source_line_id.req_layer_7_variant_id',
        string='Layer 7 Thickness',
        readonly=True,
    )
    layer_7_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_7_thickness',
        string='Layer 7 Thickness (Microns)',
        readonly=True,
    )
    layer_8_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_8_product_tmpl_id',
        string='Layer 8',
        readonly=True,
    )
    layer_8_variant_id = fields.Many2one(
        related='source_line_id.req_layer_8_variant_id',
        string='Layer 8 Thickness',
        readonly=True,
    )
    layer_8_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_8_thickness',
        string='Layer 8 Thickness (Microns)',
        readonly=True,
    )
    layer_9_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_9_product_tmpl_id',
        string='Layer 9',
        readonly=True,
    )
    layer_9_variant_id = fields.Many2one(
        related='source_line_id.req_layer_9_variant_id',
        string='Layer 9 Thickness',
        readonly=True,
    )
    layer_9_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_9_thickness',
        string='Layer 9 Thickness (Microns)',
        readonly=True,
    )
    layer_10_product_tmpl_id = fields.Many2one(
        related='source_line_id.req_layer_10_product_tmpl_id',
        string='Layer 10',
        readonly=True,
    )
    layer_10_variant_id = fields.Many2one(
        related='source_line_id.req_layer_10_variant_id',
        string='Layer 10 Thickness',
        readonly=True,
    )
    layer_10_thickness = fields.Float(
        related='source_line_id.requirement_specification_id.layer_10_thickness',
        string='Layer 10 Thickness (Microns)',
        readonly=True,
    )
    snapshot = fields.Json(string='Specification Snapshot', readonly=True)
    # Preserve the previous live-related field for existing integrations.
    design_document_line_ids = fields.One2many(
        related='source_line_id.requirement_specification_id.design_document_line_ids',
        string='Design Documents',
        readonly=True,
    )
    gdn_document_line_ids = fields.One2many(
        'sale.gdn.document.line',
        'gdn_configuration_id',
        string='GDN Documents',
        copy=False,
        help='Editable document types and multiple attachments for this GDN.',
    )
    document_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_configuration_attachment_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='GDN Documents',
        copy=False,
        help='Upload one or more files related to this GDN.',
    )

    doc_raw_file_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_raw_file_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Raw File',
        copy=False,
    )
    doc_customer_approved_file_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_cust_approved_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Customer Approved File',
        copy=False,
    )
    doc_production_layout_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_prod_layout_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Production Layout',
        copy=False,
    )
    doc_plate_layout_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_plate_layout_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Plate Layout',
        copy=False,
    )

    doc_digital_print_file_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_digital_print_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Digital Print File',
        copy=False,
    )
    doc_color_separation_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_cfg_color_separation_rel',
        'gdn_configuration_id',
        'attachment_id',
        string='Color Separation',
        copy=False,
    )

    # Legacy category-to-attachment mappings; never create empty category rows.
    _GDN_DEFAULT_DOCUMENTS = (
        ('Raw File', 'doc_raw_file_ids'),
        ('Customer Approved File', 'doc_customer_approved_file_ids'),
        ('Digital Print File', 'doc_digital_print_file_ids'),
        ('Production Layout', 'doc_production_layout_ids'),
        ('Plate Layout', 'doc_plate_layout_ids'),
        ('Color Separation', 'doc_color_separation_ids'),
    )

    @api.model_create_multi
    def create(self, vals_list):
        gdns = super().create(vals_list)
        gdns._sync_document_lines()
        return gdns

    def _update_gdn_source_files(self, row, source_attachment_ids, legacy_ids=()):
        """Mirror source attachments while preserving GDN-added and old files."""
        current = set(row.attachment_ids.ids)
        before = set(row.source_attachment_ids.ids)
        incoming = set(source_attachment_ids)
        desired = (current - before) | incoming | set(legacy_ids)
        updates = {}
        if current != desired:
            updates['attachment_ids'] = [(6, 0, sorted(desired))]
        if before != incoming:
            updates['source_attachment_ids'] = [(6, 0, sorted(incoming))]
        if updates:
            row.write(updates)

    def _sync_document_lines(self):
        """Sync real source/legacy files, never prepopulate empty GDN categories.

        Users may add document types and attachments through the GDN form's
        existing inline Add a line action.  The old fixed-category relations
        and the Requirement Form source files remain available/synchronized.
        """
        line_model = self.env['sale.gdn.document.line']
        aliases = {
            'raw': 'raw file',
            'raw files': 'raw file',
            'customer approved': 'customer approved file',
            'customer approval': 'customer approved file',
            'digital print': 'digital print file',
            'production': 'production layout',
            'plate': 'plate layout',
            'color separation file': 'color separation',
        }
        for gdn in self:
            by_name = {}
            for row in gdn.gdn_document_line_ids:
                label = (row.document_type or '').strip().casefold()
                if label and label not in by_name:
                    by_name[label] = row

            # Only categories with uploaded files (or an existing manual line)
            # should appear.  Keep old fixed-category attachments accessible.
            legacy = {
                name.casefold(): set(gdn[field_name].ids)
                for name, field_name in self._GDN_DEFAULT_DOCUMENTS
            }
            source_files = {key: set() for key in legacy}

            spec = gdn.source_line_id.requirement_specification_id
            if spec:
                for source_row in spec.design_document_line_ids:
                    source_name = (source_row.document_type or '').strip()
                    if not source_name:
                        continue
                    key = aliases.get(source_name.casefold(), source_name.casefold())
                    if key in source_files:
                        source_files[key].update(source_row.attachment_ids.ids)
                        continue

                    # Retain the existing synchronization for custom source
                    # document types without affecting GDN-only uploads.
                    row = line_model.search([
                        ('gdn_configuration_id', '=', gdn.id),
                        ('source_design_document_line_id', '=', source_row.id),
                    ], limit=1)
                    if not row:
                        row = line_model.create({
                            'gdn_configuration_id': gdn.id,
                            'sequence': 100 + source_row.sequence,
                            'document_type': source_name,
                            'source_design_document_line_id': source_row.id,
                        })
                    elif row.document_type != source_name:
                        row.document_type = source_name
                    self._update_gdn_source_files(row, source_row.attachment_ids.ids)

            for index, (name, _field_name) in enumerate(self._GDN_DEFAULT_DOCUMENTS):
                key = name.casefold()
                row = by_name.get(key)
                if not row and not legacy[key] and not source_files[key]:
                    continue
                if not row:
                    row = line_model.create({
                        'gdn_configuration_id': gdn.id,
                        'sequence': (index + 1) * 10,
                        'document_type': name,
                    })
                self._update_gdn_source_files(row, source_files[key], legacy[key])

            # Previously uncategorized GDN files remain accessible in the list.
            if gdn.document_attachment_ids:
                other = by_name.get('other documents')
                if not other:
                    other = line_model.create({
                        'gdn_configuration_id': gdn.id,
                        'sequence': 200,
                        'document_type': 'Other Documents',
                    })
                current = set(other.attachment_ids.ids)
                missing = set(gdn.document_attachment_ids.ids) - current
                if missing:
                    other.write({
                        'attachment_ids': [(4, att_id) for att_id in sorted(missing)],
                    })

    @api.model
    def _bootstrap_existing_gdn_document_lines(self):
        """Run on module upgrade for existing GDNs; safe to run repeatedly."""
        gdns = self.search([])
        first_bootstrap = gdns.filtered(lambda gdn: not gdn.gdn_document_line_ids)
        gdns._sync_document_lines()
        # Older module versions created six empty GDN document rows on every
        # record.  Remove only empty fixed-category placeholders during upgrade;
        # never unlink rows containing GDN/source files or custom categories.
        default_labels = {
            name.casefold() for name, _field_name in self._GDN_DEFAULT_DOCUMENTS
        }
        empty_defaults = gdns.mapped('gdn_document_line_ids').filtered(
            lambda row: (
                (row.document_type or '').strip().casefold() in default_labels
                and not row.attachment_ids
                and not row.source_attachment_ids
                and not row.source_design_document_line_id
            )
        )
        if empty_defaults:
            empty_defaults.unlink()
        # Preserve old displayed values only once, then let GDN users edit them.
        for gdn in first_bootstrap:
            source_line = gdn.source_line_id
            values = {}
            if source_line:
                if not gdn.print_type_id and source_line.req_print_type_id:
                    values['print_type_id'] = source_line.req_print_type_id.id
                if not gdn.no_of_colors and source_line.req_no_of_colors:
                    values['no_of_colors'] = source_line.req_no_of_colors
            if values:
                gdn.write(values)
        return True

    _sql_constraints = [
        (
            'sale_gdn_configuration_number_unique',
            'unique(gdn_number)',
            'The GDN Number must be unique.',
        ),
    ]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    requirement_form_id = fields.Many2one(
        'crm.requirement.form',
        string='Requirement Form',
        copy=True,
        index=True,
        ondelete='set null',
    )
    has_existing_gdn = fields.Boolean(
        string='Has Existing GDN',
        compute='_compute_has_existing_gdn',
    )
    job_code_summary = fields.Char(
        string='Job Code',
        compute='_compute_line_reference_summaries',
        store=True,
        help='Comma-separated Job Codes from this Sale Order lines.',
    )
    gdn_number_summary = fields.Char(
        string='GDN Number',
        compute='_compute_line_reference_summaries',
        store=True,
        help='Comma-separated GDN Numbers from this Sale Order lines.',
    )

    @api.depends('order_line.job_code', 'order_line.gdn_number')
    def _compute_line_reference_summaries(self):
        for order in self:
            job_codes = []
            gdn_numbers = []
            for line in order.order_line.filtered(lambda item: not item.display_type):
                if line.job_code and line.job_code not in job_codes:
                    job_codes.append(line.job_code)
                if line.gdn_number and line.gdn_number not in gdn_numbers:
                    gdn_numbers.append(line.gdn_number)
            order.job_code_summary = ', '.join(job_codes)
            order.gdn_number_summary = ', '.join(gdn_numbers)

    @api.onchange('requirement_form_id')
    def _onchange_requirement_form_payment_term(self):
        for order in self:
            if order.requirement_form_id.payment_term_id:
                order.payment_term_id = order.requirement_form_id.payment_term_id
            if order.requirement_form_id:
                incoterm = order.requirement_form_id._get_sale_incoterm()
                if incoterm:
                    order.incoterm = incoterm

    @api.depends('partner_id')
    def _compute_has_existing_gdn(self):
        commercial_partners = self.mapped('partner_id.commercial_partner_id')
        configured_partner_ids = set()
        if commercial_partners:
            configurations = self.env['sale.gdn.configuration'].search([
                ('partner_id', 'in', commercial_partners.ids),
            ])
            configured_partner_ids = set(configurations.mapped('partner_id').ids)

        for order in self:
            commercial_partner = order.partner_id.commercial_partner_id
            order.has_existing_gdn = bool(
                commercial_partner
                and commercial_partner.id in configured_partner_ids
            )

    def action_open_requirement_form(self):
        self.ensure_one()
        if not self.requirement_form_id:
            raise ValidationError(_('No Requirement Form is linked to this Sale Order.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requirement Form'),
            'res_model': 'crm.requirement.form',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'crm_requirement_form.crm_requirement_form_form'
            ).id,
            'res_id': self.requirement_form_id.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def _ensure_requirement_customer_codes(self):
        """Ensure a Customer Code for both REQ-driven and direct Sale Orders.

        A Sale Order is allowed to start directly from Sales without a CRM lead
        or Requirement Form.  In that flow the selected customer is still the
        source of truth and receives a Customer Code when one is needed for Job
        Code / GDN generation.  Requirement-linked orders keep the previous
        synchronization behavior.
        """
        for order in self:
            partner = order.partner_id.commercial_partner_id
            if not partner:
                continue

            requirement = order.requirement_form_id
            customer_code = False

            if requirement:
                customer_code = requirement._ensure_sales_customer_code()

            if not customer_code:
                country = partner.country_id
                if requirement and requirement.address_country:
                    country = country or requirement.address_country
                customer_code = partner._ensure_customer_code_for_sales(
                    country=country
                )

            if requirement and customer_code:
                if requirement.customer_id != customer_code:
                    requirement.write({'customer_id': customer_code})
                if (
                    requirement.lead_id
                    and requirement.lead_id.generated_customer_id
                    != customer_code
                ):
                    requirement.lead_id.with_context(
                        skip_customer_code_partner_sync=True
                    ).write({'generated_customer_id': customer_code})

        return True

    _UTM_FIELDS = ('campaign_id', 'medium_id', 'source_id')

    def init(self):
        """Back-fill Campaign/Medium/Source (from Opportunity) and Incoterm (from Requirement Form)."""
        super().init()
        self.env.cr.execute("SELECT to_regclass('crm_requirement_form')")
        if self.env.cr.fetchone()[0]:
            self.env.cr.execute("""
                UPDATE sale_order so
                   SET incoterm = inc.id
                  FROM crm_requirement_form form
                  JOIN account_incoterms inc
                    ON UPPER(inc.code) = UPPER(form.delivery_terms)
                 WHERE so.requirement_form_id = form.id
                   AND so.state IN ('draft', 'sent')
                   AND so.incoterm IS NULL
                   AND COALESCE(form.delivery_terms, '') <> ''
            """)
        for column in self._UTM_FIELDS:
            self.env.cr.execute(f"""
                UPDATE sale_order so
                   SET {column} = lead.{column}
                  FROM crm_lead lead
                 WHERE so.opportunity_id = lead.id
                   AND so.state IN ('draft', 'sent')
                   AND so.{column} IS NULL
                   AND lead.{column} IS NOT NULL
            """)

    @api.model
    def _utm_values_from_opportunity(self, opportunity_id, vals=None, overwrite=False):
        """Return Campaign/Medium/Source of the Opportunity for a Sale Order."""
        lead = self.env['crm.lead'].browse(opportunity_id).exists()
        result = {}
        for field_name in self._UTM_FIELDS:
            if not lead[field_name]:
                continue
            if vals and vals.get(field_name) and not overwrite:
                continue
            result[field_name] = lead[field_name].id
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('opportunity_id'):
                vals.update(
                    self._utm_values_from_opportunity(
                        vals['opportunity_id'], vals=vals
                    )
                )
            if vals.get('requirement_form_id') and not vals.get('incoterm'):
                form = self.env['crm.requirement.form'].browse(
                    vals['requirement_form_id']
                ).exists()
                incoterm = form._get_sale_incoterm() if form else False
                if incoterm:
                    vals['incoterm'] = incoterm.id
        orders = super().create(vals_list)
        # Do not force Customer Code generation merely by opening/saving a
        # direct quotation.  Codes are ensured when confirmation or GDN
        # generation actually needs them.  Requirement-linked quotations keep
        # their historical synchronization behavior.
        orders.filtered(
            lambda order: order.requirement_form_id
        )._ensure_requirement_customer_codes()
        return orders

    def write(self, vals):
        if vals.get('requirement_form_id') and 'incoterm' not in vals:
            form = self.env['crm.requirement.form'].browse(
                vals['requirement_form_id']
            ).exists()
            incoterm = form._get_sale_incoterm() if form else False
            if incoterm:
                vals = dict(vals, incoterm=incoterm.id)
        if vals.get('opportunity_id'):
            # A newly linked Opportunity is the source of Campaign/Medium/Source
            # unless the caller sends them explicitly.
            vals = dict(vals)
            for key, value in self._utm_values_from_opportunity(
                vals['opportunity_id']
            ).items():
                vals.setdefault(key, value)
        return super().write(vals)

    @api.onchange('opportunity_id')
    def _onchange_opportunity_fetch_utm(self):
        for order in self:
            lead = order.opportunity_id
            if not lead:
                continue
            for field_name in self._UTM_FIELDS:
                if lead[field_name]:
                    order[field_name] = lead[field_name]

    @api.onchange('partner_id')
    def _onchange_partner_clear_incompatible_gdns(self):
        """Keep direct Sale Order GDN selection safely customer-scoped."""
        for order in self:
            commercial_partner = order.partner_id.commercial_partner_id
            for line in order.order_line.filtered(
                lambda item: not item.display_type and item.gdn_configuration_id
            ):
                gdn_partner = (
                    line.gdn_configuration_id.partner_id.commercial_partner_id
                )
                if (
                    (not commercial_partner or gdn_partner != commercial_partner)
                    and not line._is_source_repeat_gdn()
                ):
                    line.gdn_configuration_id = False
                    line.gdn_number = False

    def _generate_missing_job_codes(self):
        """Generate customer-wise Job Codes for non-display order lines."""
        SaleLine = self.env['sale.order.line'].sudo()
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.display_type and not line.job_code)
            if not lines:
                continue

            order._ensure_requirement_customer_codes()
            partner = order.partner_id.commercial_partner_id
            requirement = order.requirement_form_id
            customer_code = (
                partner.customer_code
                or (requirement.customer_id if requirement else False)
                or ''
            ).strip()
            if not customer_code:
                raise ValidationError(_('Customer Code is required before confirming the Sale Order.'))

            customer_first_part = customer_code.split('-', 1)[0].strip()
            customer_last_part = customer_code.rsplit('-', 1)[-1].strip()
            if not customer_first_part or not customer_last_part:
                raise ValidationError(
                    _('Customer Code format is invalid: %s') % customer_code
                )

            # New format:
            # 1 - customer code first part - customer code last part - serial - 00
            # Example: customer code 02-00053 -> 1-02-00053-0001-00
            job_prefix = f'1-{customer_first_part}-{customer_last_part}-'

            # Keep serial continuity with both previously generated formats:
            # 1-00053-0001-00 and 00053-0001-00.
            previous_prefix = f'1-{customer_last_part}-'
            legacy_prefix = f'{customer_last_part}-'
            max_serial = 0
            existing_codes = SaleLine.search([
                ('order_id.partner_id.commercial_partner_id', '=', partner.id),
                '|',
                '|',
                ('job_code', '=like', f'{job_prefix}%-00'),
                ('job_code', '=like', f'{previous_prefix}%-00'),
                ('job_code', '=like', f'{legacy_prefix}%-00'),
            ]).mapped('job_code')
            for code in existing_codes:
                parts = (code or '').split('-')
                if (
                    len(parts) == 5
                    and parts[0] == '1'
                    and parts[1] == customer_first_part
                    and parts[2] == customer_last_part
                    and parts[3].isdigit()
                    and parts[4] == '00'
                ):
                    max_serial = max(max_serial, int(parts[3]))
                elif (
                    len(parts) == 4
                    and parts[0] == '1'
                    and parts[1] == customer_last_part
                    and parts[2].isdigit()
                    and parts[3] == '00'
                ):
                    max_serial = max(max_serial, int(parts[2]))
                elif (
                    len(parts) == 3
                    and parts[0] == customer_last_part
                    and parts[1].isdigit()
                    and parts[2] == '00'
                ):
                    max_serial = max(max_serial, int(parts[1]))

            sorted_lines = lines.sorted(key=lambda item: (item.sequence, item.id))
            for serial_offset, line in enumerate(sorted_lines, start=1):
                serial = max_serial + serial_offset
                line.job_code = f'{job_prefix}{serial:04d}-00'

    def _check_gdn_generated_before_confirm(self):
        """Block confirmation while any product line has no GDN Number."""
        for order in self:
            missing = order.order_line.filtered(
                lambda line: not line.display_type
                and line.product_id
                and not (line.gdn_configuration_id or line.gdn_number)
            )
            if missing:
                names = '\n'.join(
                    '- %s' % (line.product_id.display_name or line.name)
                    for line in missing
                )
                raise UserError(_(
                    'Please generate the GDN Number before confirming the '
                    'Sale Order %(order)s.\n\nGDN is missing for:\n%(lines)s',
                    order=order.name,
                    lines=names,
                ))

    def action_confirm(self):
        """Require GDN, ensure Customer Code, confirm, then assign Job Codes."""
        self._check_gdn_generated_before_confirm()
        self._ensure_requirement_customer_codes()
        result = super().action_confirm()
        self._generate_missing_job_codes()
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Independent visibility flag for the read-only Job Code SQL-view row.
    # Existing Sale Order Lines and business processes remain active.
    job_code_disabled = fields.Boolean(
        string='Job Code Disabled', default=False, copy=False,
    )

    # Manually entered production configuration, stored per Sale Order line.
    job_process_sequence = fields.Many2many(
        'crm.job.production.process',
        'crm_job_process_sale_line_rel',
        'sale_line_id', 'process_id',
        string='Process Sequence',
    )
    job_one_up_size = fields.Char(string='One Up Size')
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
    # Pouch-only manual dimensions; source bag length/width stay on req_*.
    job_pouch_side_gusset = fields.Float(string='Side Gusset (mm)', copy=False)
    job_pouch_bottom_gusset = fields.Float(string='Bottom Gusset (mm)', copy=False)

    job_quality_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sale_order_line_job_quality_attachment_rel',
        'sale_line_id',
        'attachment_id',
        string='Quality Documents',
        copy=False,
        help='Files uploaded only for this Job Code; not linked to GDN or Requirement documents.',
    )

    # Legacy document links are preserved to avoid deleting historical data,
    # but are no longer displayed, populated or used by the Job Code form.
    job_code_document_line_ids = fields.One2many(
        'sale.job.code.document.line',
        'source_line_id',
        string='Job Code Design Documents',
        copy=False,
    )

    def _sync_job_code_document_rows(self):
        """Idempotently link Job Code rows to original specification files.

        Existing uploads remain on Product Specifications, so REQ -> GDN
        synchronization is not changed.  This creates only missing links.
        """
        proxy_model = self.env['sale.job.code.document.line'].sudo()
        for line in self.filtered(
            lambda rec: rec.job_code and rec.requirement_specification_id
        ):
            specification = line.requirement_specification_id
            source_documents = specification.design_document_line_ids
            wanted_ids = set(source_documents.ids)
            stale = line.job_code_document_line_ids.filtered(
                lambda row: row.source_design_document_line_id.id not in wanted_ids
            )
            if stale:
                stale.sudo().with_context(
                    keep_source_design_document=True
                ).unlink()
            existing_ids = set(
                line.job_code_document_line_ids.mapped(
                    'source_design_document_line_id'
                ).ids
            )
            for document in source_documents:
                if document.id not in existing_ids:
                    proxy_model.with_context(
                        skip_job_code_document_bootstrap=True
                    ).create({
                        'source_line_id': line.id,
                        'source_design_document_line_id': document.id,
                    })
        return True

    @api.model
    def _bootstrap_existing_job_code_documents(self):
        """Add links for already confirmed orders during module upgrade."""
        existing_lines = self.sudo().search([
            ('job_code', '!=', False),
            ('requirement_specification_id', '!=', False),
        ])
        existing_lines._sync_job_code_document_rows()
        return True

    job_customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='order_id.partner_id.commercial_partner_id',
        store=True,
        readonly=True,
        index=True,
    )

    job_code = fields.Char(
        string='Job Code',
        copy=False,
        readonly=True,
        index=True,
        help=(
            'Generated on Sale Order confirmation: 1 - customer code first part - '
            'customer code last part - serial - 00.'
        ),
    )

    job_configuration_id = fields.Many2one(
        'sale.job.code.configuration',
        string='Job Code',
        compute='_compute_job_configuration_id',
        readonly=True,
        help='Open the read-only Job Code Configuration for this Sale Order line.',
    )

    @api.depends('job_code')
    def _compute_job_configuration_id(self):
        for line in self:
            line.job_configuration_id = (
                line.id
                if line.job_code and isinstance(line.id, int)
                else False
            )

    job_code_link = fields.Html(
        string='Job Code',
        compute='_compute_configuration_links',
        readonly=True,
        sanitize=False,
    )
    gdn_number_link = fields.Html(
        string='GDN Number',
        compute='_compute_configuration_links',
        readonly=True,
        sanitize=False,
    )

    @api.depends('job_code', 'gdn_number', 'gdn_configuration_id')
    def _compute_configuration_links(self):
        for line in self:
            line.job_code_link = False
            line.gdn_number_link = False

            if line.job_code and isinstance(line.id, int):
                line.job_code_link = (
                    '<a href="/web#id=%s&amp;model=sale.job.code.configuration'
                    '&amp;view_type=form" class="fw-semibold">%s</a>'
                    % (line.id, line.job_code)
                )

            if line.gdn_number and line.gdn_configuration_id:
                line.gdn_number_link = (
                    '<a href="/web#id=%s&amp;model=sale.gdn.configuration'
                    '&amp;view_type=form" class="fw-semibold">%s</a>'
                    % (line.gdn_configuration_id.id, line.gdn_number)
                )

    gdn_configuration_id = fields.Many2one(
        'sale.gdn.configuration',
        string='Existing GDN',
        copy=True,
        index=True,
        ondelete='set null',
    )
    gdn_number = fields.Char(
        string='GDN Number',
        copy=True,
        readonly=True,
        index=True,
    )
    gdn_customer_id = fields.Many2one(
        'res.partner',
        string='GDN Customer',
        related='order_id.partner_id.commercial_partner_id',
        readonly=True,
    )
    gdn_order_partner_id = fields.Many2one(
        'res.partner',
        string='Order Customer',
        related='order_id.partner_id',
        readonly=True,
    )
    gdn_order_state = fields.Selection(
        related='order_id.state',
        string='Sale Order State',
        readonly=True,
    )
    gdn_from_existing = fields.Boolean(
        string='GDN Loaded From Existing Configuration',
        compute='_compute_gdn_from_existing',
    )
    requirement_specification_id = fields.Many2one(
        'crm.requirement.specification',
        string='Requirement Specification',
        copy=False,
        index=True,
        ondelete='set null',
    )
    req_design_name = fields.Char(string='Design Name', copy=False)
    req_design_dimension_uom = fields.Selection(
        [
            ('mm', 'MM'),
            ('cm', 'CM'),
            ('inch', 'Inch'),
            ('meters', 'Meters'),
        ],
        string='Design Dimension UOM',
        copy=False,
    )
    req_design_no = fields.Integer(string='No. Designs', copy=False)
    req_color_reference = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Color Reference',
        copy=False,
    )
    req_color_reference_type = fields.Selection(
        [('physical', 'Physical'), ('pantone', 'Pantone')],
        string='Color Reference Type',
        copy=False,
    )
    req_print_type_id = fields.Many2one(
        'crm.requirement.print.type.option',
        string='Print Type',
        copy=False,
        ondelete='restrict',
    )
    req_no_of_colors = fields.Integer(string='No of Colors', copy=False)
    req_quantity = fields.Integer(string='Quantity', copy=False)
    req_quantity_uom = fields.Selection(
        [('pcs', 'PCS'), ('kg', 'KG'), ('lm', 'LM')],
        string='Legacy Quantity UOM',
        copy=False,
    )
    req_quantity_uom_id = fields.Many2one(
        'uom.uom',
        string='Quantity UOM',
        copy=False,
        ondelete='restrict',
    )
    req_fg_type = fields.Selection(
        [('bag', 'Bag'), ('roll', 'Roll')],
        string='FG Type',
        copy=False,
    )
    req_roll_type = fields.Selection(
        [('roll', 'Roll Stock'), ('label', 'Label')],
        string='Roll Type',
        copy=False,
    )
    req_bag_type_id = fields.Many2one(
        'crm.requirement.bag.type.option',
        string='Legacy Bag Type',
        copy=False,
    )
    req_bag_type_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        copy=False,
    )
    req_length = fields.Float(string='Length (mm)', copy=False)
    req_width = fields.Integer(string='Width (mm)', copy=False)
    req_gusset = fields.Float(string='Gusset (mm)', copy=False)
    req_coil_width_mm = fields.Float(string='Coil Width (mm)', copy=False)
    req_cutoff_length_mm = fields.Float(string='Cutoff Length (mm)', copy=False)
    req_final_roll_direction = fields.Char(
        string='Final Roll Direction', copy=False
    )
    req_final_roll_weight_kg = fields.Float(
        string='Final Roll Weight (kg)', copy=False
    )
    req_final_roll_od_mm = fields.Float(string='Final Roll OD (mm)', copy=False)
    req_final_roll_meters = fields.Float(string='Final Roll Meters', copy=False)
    req_core_id_mm = fields.Float(string='Core ID (mm)', copy=False)
    req_core_thickness_mm = fields.Float(
        string='Core Thickness (mm)', copy=False
    )
    req_core_type = fields.Char(string='Core Type', copy=False)

    req_layer_1_product_tmpl_id = fields.Many2one('product.template', string='Layer 1', copy=False)
    req_layer_1_variant_id = fields.Many2one('product.product', string='Layer 1 Thickness', copy=False)
    req_layer_2_product_tmpl_id = fields.Many2one('product.template', string='Layer 2', copy=False)
    req_layer_2_variant_id = fields.Many2one('product.product', string='Layer 2 Thickness', copy=False)
    req_layer_3_product_tmpl_id = fields.Many2one('product.template', string='Layer 3', copy=False)
    req_layer_3_variant_id = fields.Many2one('product.product', string='Layer 3 Thickness', copy=False)
    req_layer_4_product_tmpl_id = fields.Many2one('product.template', string='Layer 4', copy=False)
    req_layer_4_variant_id = fields.Many2one('product.product', string='Layer 4 Thickness', copy=False)
    req_layer_5_product_tmpl_id = fields.Many2one('product.template', string='Layer 5', copy=False)
    req_layer_5_variant_id = fields.Many2one('product.product', string='Layer 5 Thickness', copy=False)
    req_layer_6_product_tmpl_id = fields.Many2one('product.template', string='Layer 6', copy=False)
    req_layer_6_variant_id = fields.Many2one('product.product', string='Layer 6 Thickness', copy=False)
    req_layer_7_product_tmpl_id = fields.Many2one('product.template', string='Layer 7', copy=False)
    req_layer_7_variant_id = fields.Many2one('product.product', string='Layer 7 Thickness', copy=False)
    req_layer_8_product_tmpl_id = fields.Many2one('product.template', string='Layer 8', copy=False)
    req_layer_8_variant_id = fields.Many2one('product.product', string='Layer 8 Thickness', copy=False)
    req_layer_9_product_tmpl_id = fields.Many2one('product.template', string='Layer 9', copy=False)
    req_layer_9_variant_id = fields.Many2one('product.product', string='Layer 9 Thickness', copy=False)
    req_layer_10_product_tmpl_id = fields.Many2one('product.template', string='Layer 10', copy=False)
    req_layer_10_variant_id = fields.Many2one('product.product', string='Layer 10 Thickness', copy=False)

    req_total_thickness = fields.Float(string='Total Thickness (Microns)', copy=False)
    req_print_finish_ids = fields.Many2many(
        'crm.requirement.print.finish.option',
        'sale_order_line_req_print_finish_rel',
        'line_id',
        'option_id',
        string='Legacy Print and Finish',
        copy=False,
    )
    req_print_finish_id = fields.Many2one(
        'crm.requirement.print.finish.option',
        string='Print and Finish',
        copy=False,
        domain=[('active', '=', True)],
    )
    req_feature_ids = fields.Many2many(
        'crm.requirement.feature.option',
        'sale_order_line_req_feature_rel',
        'line_id',
        'option_id',
        string='Features',
        copy=False,
    )
    req_additional_requirements = fields.Text(string='Additional Requirements', copy=False)

    @api.onchange('req_fg_type')
    def _onchange_req_fg_type_filter_product(self):
        """Keep the selected Sale product aligned with the FG Type."""
        for line in self:
            if line.display_type:
                continue

            if line.req_fg_type == 'roll':
                line.req_roll_type = line.req_roll_type or 'roll'
            else:
                line.req_roll_type = False

            product_tmpl = line.product_id.product_tmpl_id
            if (
                product_tmpl
                and product_tmpl.requirement_fg_type != line.req_fg_type
            ):
                line.product_id = False
                line.req_bag_type_product_tmpl_id = False

    @api.onchange('product_id')
    def _onchange_requirement_fg_product(self):
        """Sync the selected Bag/Roll product back to requirement fields."""
        for line in self:
            if line.display_type or not line.product_id:
                continue

            product_tmpl = line.product_id.product_tmpl_id
            fg_type = product_tmpl.requirement_fg_type
            if not fg_type:
                continue

            if line.req_fg_type and line.req_fg_type != fg_type:
                line.product_id = False
                line.req_bag_type_product_tmpl_id = False
                continue

            line.req_fg_type = fg_type
            line.req_bag_type_product_tmpl_id = product_tmpl

            if fg_type == 'roll':
                code = (
                    product_tmpl.requirement_bag_type_code or ''
                ).strip().upper()
                if code == 'LBL':
                    line.req_roll_type = 'label'
                elif code == 'RS':
                    line.req_roll_type = 'roll'
                else:
                    line.req_roll_type = line.req_roll_type or 'roll'
            else:
                line.req_roll_type = False

    @api.onchange('req_quantity')
    def _onchange_req_quantity_sync_sale_quantity(self):
        """Keep custom QTY (PCS) linked with the standard sale quantity."""
        for line in self:
            if not line.display_type:
                line.product_uom_qty = line.req_quantity or 0.0

    @api.onchange('product_uom_qty')
    def _onchange_sale_quantity_sync_req_quantity(self):
        """Keep the requirement quantity in sync when standard QTY changes."""
        for line in self:
            if not line.display_type:
                line.req_quantity = int(line.product_uom_qty or 0.0)

    @api.depends(
        'gdn_configuration_id',
        'gdn_configuration_id.source_line_id',
    )
    def _compute_gdn_from_existing(self):
        """Lock only lines that reuse a GDN created from another line."""
        for line in self:
            configuration = line.gdn_configuration_id
            line.gdn_from_existing = bool(
                configuration
                and configuration.source_line_id
                and configuration.source_line_id != line._origin
            ) or bool(
                configuration
                and not configuration.source_line_id
            )

    def _get_requirement_gdn_bag_code(self):
        self.ensure_one()
        product_tmpl = self.req_bag_type_product_tmpl_id
        if (
            not product_tmpl
            and self.product_id.product_tmpl_id.requirement_fg_type
        ):
            product_tmpl = self.product_id.product_tmpl_id
        if not product_tmpl:
            return False
        return product_tmpl._get_requirement_bag_code()

    def _prepare_gdn_snapshot(self):
        self.ensure_one()
        snapshot = {
            'product_id': self.product_id.id or False,
            'product_uom_id': self.product_uom_id.id or False,
            'price_unit': self.price_unit or 0.0,
            'discount': self.discount or 0.0,
            'tax_ids': self.tax_ids.ids,
            'name': self.name or False,
            'requirement_specification_id': self.requirement_specification_id.id or False,
            'req_design_name': self.req_design_name or False,
            'req_design_dimension_uom': self.req_design_dimension_uom or 'mm',
            'req_design_no': self.req_design_no or 0,
            'req_color_reference': self.req_color_reference or False,
            'req_color_reference_type': self.req_color_reference_type or False,
            'req_print_type_id': self.req_print_type_id.id or False,
            'req_no_of_colors': self.req_no_of_colors or 0,
            'req_quantity': self.req_quantity or 0,
            'req_quantity_uom': self.req_quantity_uom or False,
            'req_quantity_uom_id': self.req_quantity_uom_id.id or False,
            'req_fg_type': self.req_fg_type or False,
            'req_roll_type': self.req_roll_type or False,
            'req_bag_type_id': self.req_bag_type_id.id or False,
            'req_bag_type_product_tmpl_id': self.req_bag_type_product_tmpl_id.id or False,
            'req_length': self.req_length or 0.0,
            'req_width': self.req_width or 0,
            'req_gusset': self.req_gusset or 0.0,
            'req_coil_width_mm': self.req_coil_width_mm or 0.0,
            'req_cutoff_length_mm': self.req_cutoff_length_mm or 0.0,
            'req_final_roll_direction': self.req_final_roll_direction or False,
            'req_final_roll_weight_kg': self.req_final_roll_weight_kg or 0.0,
            'req_final_roll_od_mm': self.req_final_roll_od_mm or 0.0,
            'req_final_roll_meters': self.req_final_roll_meters or 0.0,
            'req_core_id_mm': self.req_core_id_mm or 0.0,
            'req_core_thickness_mm': self.req_core_thickness_mm or 0.0,
            'req_core_type': self.req_core_type or False,
            'req_total_thickness': self.req_total_thickness or 0.0,
            'req_print_finish_id': self.req_print_finish_id.id or False,
            'req_feature_ids': self.req_feature_ids.ids,
            'req_additional_requirements': self.req_additional_requirements or False,
        }
        for layer_no in range(1, 11):
            template = self[f'req_layer_{layer_no}_product_tmpl_id']
            variant = self[f'req_layer_{layer_no}_variant_id']
            snapshot[f'req_layer_{layer_no}_product_tmpl_id'] = template.id or False
            snapshot[f'req_layer_{layer_no}_variant_id'] = variant.id or False
        return snapshot

    def _apply_gdn_configuration(self, configuration):
        """Load a selected GDN as a complete Sale Order line snapshot.

        This is intentionally sufficient for the direct Sales flow: select a
        Customer, add a line, choose an existing GDN, and the line is populated
        without requiring a CRM lead or Requirement Form.
        """
        self.ensure_one()
        values = dict(configuration.snapshot or {})
        source_line = configuration.source_line_id.exists()

        # A direct Sale Order intentionally has no Requirement Form.  Reusing
        # an old GDN must not silently attach the new line to the old REQ design
        # (which could otherwise make later writes update that historical REQ).
        if not self.order_id.requirement_form_id:
            values.pop('requirement_specification_id', None)

        # Older GDNs may predate commercial fields in the JSON snapshot.  Use
        # their source line as a backward-compatible fallback so direct reuse is
        # still smooth after upgrading the module.
        if source_line:
            values.setdefault('product_id', source_line.product_id.id or False)
            values.setdefault(
                'product_uom_id', source_line.product_uom_id.id or False
            )
            values.setdefault('price_unit', source_line.price_unit or 0.0)
            values.setdefault('discount', source_line.discount or 0.0)
            values.setdefault('tax_ids', source_line.tax_ids.ids)
            values.setdefault('name', source_line.name or False)
            values.setdefault(
                'req_quantity',
                int(source_line.product_uom_qty or 0.0),
            )
            values.setdefault(
                'req_quantity_uom_id',
                source_line.product_uom_id.id or False,
            )

        feature_ids = values.pop('req_feature_ids', [])
        values['req_feature_ids'] = (
            [(6, 0, feature_ids)] if feature_ids else [(5, 0, 0)]
        )

        tax_ids = values.pop('tax_ids', [])
        values['tax_ids'] = (
            [(6, 0, tax_ids)] if tax_ids else [(5, 0, 0)]
        )

        print_finish_id = values.get('req_print_finish_id')
        values['req_print_finish_ids'] = (
            [(6, 0, [print_finish_id])] if print_finish_id else [(5, 0, 0)]
        )
        values['gdn_number'] = configuration.gdn_number
        values['product_uom_qty'] = values.get('req_quantity', 0) or 0.0
        if not values.get('product_uom_id') and values.get('req_quantity_uom_id'):
            values['product_uom_id'] = values['req_quantity_uom_id']

        self.update(values)

    def action_generate_gdn(self):
        allowed_states = {'draft', 'sent', 'sale'}
        for line in self:
            if line.display_type:
                continue
            if line.order_id.state not in allowed_states:
                raise ValidationError(_(
                    'GDN can only be generated in Quotation, Quotation Sent, or Sale Order status.'
                ))
            if line.gdn_configuration_id or line.gdn_number:
                raise ValidationError(_('A GDN Number is already assigned to this line.'))

            line.order_id._ensure_requirement_customer_codes()
            partner = line.order_id.partner_id.commercial_partner_id
            requirement = line.order_id.requirement_form_id
            customer_code = (
                (requirement.customer_id if requirement else False)
                or partner.customer_code
            )
            if not customer_code:
                raise ValidationError(_('Customer Code is required before generating GDN.'))

            bag_code = line._get_requirement_gdn_bag_code()
            if not bag_code:
                raise ValidationError(
                    _('A configured FG product is required on the sale order line to generate GDN.')
                )

            job_number = self.env['ir.sequence'].next_by_code('crm.requirement.gdn.job')
            if not job_number:
                raise ValidationError(_('GDN Job Number sequence is not configured.'))

            gdn_number = f'{customer_code}-{bag_code}-{job_number}'
            configuration = self.env['sale.gdn.configuration'].create({
                'gdn_number': gdn_number,
                'partner_id': partner.id,
                'fg_type': line.req_fg_type or False,
                'roll_type': line.req_roll_type or False,
                'bag_type_product_tmpl_id': line.req_bag_type_product_tmpl_id.id or False,
                'source_order_id': line.order_id.id,
                'source_line_id': line.id,
                'design_name': line.req_design_name or line.name or False,
                'design_dimension_uom': line.req_design_dimension_uom or 'mm',
                'quantity': line.req_quantity or 0,
                'quantity_uom': line.req_quantity_uom or False,
                'quantity_uom_id': line.req_quantity_uom_id.id or False,
                'length': line.req_length or 0.0,
                'width': line.req_width or 0,
                'gusset': line.req_gusset or 0.0,
                'total_thickness': line.req_total_thickness or 0.0,
                'print_finish_id': line.req_print_finish_id.id or False,
                'snapshot': line._prepare_gdn_snapshot(),
            })
            line.write({
                'gdn_configuration_id': configuration.id,
                'gdn_number': gdn_number,
            })
            if line.requirement_specification_id:
                line.requirement_specification_id._sync_documents_to_linked_gdns()
        # Returning False lets the standard Odoo form button flow refresh the
        # current record data without triggering a full client/page reload action.
        # The freshly assigned GDN configuration is therefore shown immediately.
        return False

    def _normalize_requirement_values_for_write(self, vals):
        """Keep the visible Sale Order columns and requirement fields aligned."""
        vals = dict(vals)

        if 'product_uom_qty' in vals and 'req_quantity' not in vals:
            vals['req_quantity'] = int(vals.get('product_uom_qty') or 0.0)
        elif 'req_quantity' in vals and 'product_uom_qty' not in vals:
            vals['product_uom_qty'] = vals.get('req_quantity') or 0.0

        if 'product_uom_id' in vals and 'req_quantity_uom_id' not in vals:
            vals['req_quantity_uom_id'] = vals.get('product_uom_id') or False
        elif 'req_quantity_uom_id' in vals and 'product_uom_id' not in vals:
            vals['product_uom_id'] = vals.get('req_quantity_uom_id') or False

        if 'product_id' in vals:
            product = self.env['product.product'].browse(
                vals.get('product_id')
            ).exists()
            template = product.product_tmpl_id if product else self.env['product.template']
            vals['req_bag_type_product_tmpl_id'] = template.id or False
            if template and template.requirement_fg_type:
                vals['req_fg_type'] = template.requirement_fg_type
                if template.requirement_fg_type == 'roll':
                    code = (template.requirement_bag_type_code or '').strip().upper()
                    vals['req_roll_type'] = 'label' if code == 'LBL' else 'roll'
                else:
                    vals['req_roll_type'] = False
        return vals

    def _prepare_requirement_specification_sync_values(self):
        """Translate the saved Sale Order line back to its Requirement design."""
        self.ensure_one()
        values = {
            'design_name': self.req_design_name or False,
            'design_dimension_uom': self.req_design_dimension_uom or 'mm',
            'color_reference': self.req_color_reference or False,
            'color_reference_type': self.req_color_reference_type or False,
            'print_type_id': self.req_print_type_id.id or False,
            'no_of_colors': self.req_no_of_colors or 0,
            'quantity': self.req_quantity or 0,
            'quantity_uom': self.req_quantity_uom or False,
            'quantity_uom_id': self.req_quantity_uom_id.id or False,
            'fg_type': self.req_fg_type or 'bag',
            'roll_type': self.req_roll_type or False,
            'bag_type_product_tmpl_id': (
                self.req_bag_type_product_tmpl_id.id or False
            ),
            'length': self.req_length or 0.0,
            'width': self.req_width or 0,
            'gusset': self.req_gusset or 0.0,
            'coil_width_mm': self.req_coil_width_mm or 0.0,
            'cutoff_length_mm': self.req_cutoff_length_mm or 0.0,
            'final_roll_direction': self.req_final_roll_direction or False,
            'final_roll_weight_kg': self.req_final_roll_weight_kg or 0.0,
            'final_roll_od_mm': self.req_final_roll_od_mm or 0.0,
            'final_roll_meters': self.req_final_roll_meters or 0.0,
            'core_id_mm': self.req_core_id_mm or 0.0,
            'core_thickness_mm': self.req_core_thickness_mm or 0.0,
            'core_type': self.req_core_type or False,
            'print_finish_id': self.req_print_finish_id.id or False,
            'standard_feature_ids': [(6, 0, self.req_feature_ids.ids)],
            'additional_requirements': self.req_additional_requirements or False,
        }
        highest_layer = 1
        for layer_no in range(1, 11):
            template = self[f'req_layer_{layer_no}_product_tmpl_id']
            variant = self[f'req_layer_{layer_no}_variant_id']
            values[f'layer_{layer_no}_product_tmpl_id'] = template.id or False
            values[f'layer_{layer_no}_variant_id'] = variant.id or False
            values[f'layer_{layer_no}_material'] = (
                template.display_name if template else False
            )
            values[f'layer_{layer_no}_thickness'] = (
                variant._get_requirement_layer_thickness()
                if variant
                else (template.thickness_microns if template else 0.0)
            )
            if template:
                highest_layer = layer_no
        values['layer_visible_count'] = highest_layer
        return values

    def _prepare_gdn_sync_values(self):
        """Prepare the live GDN values from the current Sale Order line."""
        self.ensure_one()
        return {
            'partner_id': self.order_id.partner_id.commercial_partner_id.id,
            'fg_type': self.req_fg_type or False,
            'roll_type': self.req_roll_type or False,
            'bag_type_product_tmpl_id': (
                self.req_bag_type_product_tmpl_id.id or False
            ),
            'source_order_id': self.order_id.id,
            'source_line_id': self.id,
            'design_name': self.req_design_name or self.name or False,
            'design_dimension_uom': self.req_design_dimension_uom or 'mm',
            'quantity': self.req_quantity or 0,
            'quantity_uom': self.req_quantity_uom or False,
            'quantity_uom_id': self.req_quantity_uom_id.id or False,
            'length': self.req_length or 0.0,
            'width': self.req_width or 0,
            'gusset': self.req_gusset or 0.0,
            'total_thickness': self.req_total_thickness or 0.0,
            'print_finish_id': self.req_print_finish_id.id or False,
            'snapshot': self._prepare_gdn_snapshot(),
        }

    def _sync_linked_requirement_and_gdn(self):
        """Propagate Sale Order line edits to REQ, GDN and Job Code views.

        Job Code Configuration is a SQL view over ``sale.order.line``, so it is
        live automatically. Requirement Specification and GDN Configuration are
        stored records and therefore need an explicit synchronization step.
        """
        for line in self.filtered(lambda item: not item.display_type):
            specification = line.requirement_specification_id
            if specification:
                specification.with_context(
                    sale_line_sync=True,
                ).write(line._prepare_requirement_specification_sync_values())

            configuration = line.gdn_configuration_id
            if (
                configuration
                and configuration.source_line_id
                and configuration.source_line_id.id == line.id
            ):
                configuration.sudo().write(line._prepare_gdn_sync_values())
        return True

    def write(self, vals):
        vals = self._normalize_requirement_values_for_write(vals)
        result = super().write(vals)
        if not self.env.context.get('skip_sale_line_linked_sync'):
            self._sync_linked_requirement_and_gdn()
        return result

    def _is_source_repeat_gdn(self):
        """Allow only a GDN belonging to this repeat job's exact source design.

        Historical GDN ownership is unchanged; the new customer may reuse
        that configuration only through a linked repeat Requirement Form.
        """
        self.ensure_one()
        specification = self.requirement_specification_id
        source = specification.source_specification_id
        form = self.order_id.requirement_form_id
        if not (
            form and form.repeat_job and specification.form_id == form
            and source and self.gdn_configuration_id
        ):
            return False
        return bool(source.sale_order_line_ids.filtered(
            lambda line: not line.display_type
            and line.gdn_configuration_id == self.gdn_configuration_id
        ))

    def _validate_gdn_configuration_customer(self):
        for line in self.filtered('gdn_configuration_id'):
            order_customer = line.order_id.partner_id.commercial_partner_id
            configuration_customer = (
                line.gdn_configuration_id.partner_id.commercial_partner_id
            )
            if (
                order_customer
                and configuration_customer
                and order_customer != configuration_customer
                and not line._is_source_repeat_gdn()
            ):
                raise ValidationError(
                    _(
                        'The selected GDN belongs to customer %(gdn_customer)s, '
                        'but this Sale Order belongs to %(order_customer)s.',
                        gdn_customer=configuration_customer.display_name,
                        order_customer=order_customer.display_name,
                    )
                )

    @api.constrains('gdn_configuration_id', 'order_id')
    def _check_gdn_configuration_customer(self):
        self._validate_gdn_configuration_customer()

    @api.onchange('gdn_configuration_id')
    def _onchange_gdn_configuration_id(self):
        for line in self:
            if line.gdn_configuration_id:
                line._validate_gdn_configuration_customer()
                line._apply_gdn_configuration(line.gdn_configuration_id)
            else:
                line.gdn_number = False
