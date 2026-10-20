import re
import uuid

from markupsafe import Markup, escape

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class CrmRequirementForm(models.Model):
    _name = 'crm.requirement.form'
    _description = 'CRM Requirement Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='REQ ID',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        tracking=True,
    )
    lead_id = fields.Many2one('crm.lead', string='Lead', tracking=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )

    customer_name = fields.Char(string='Customer Name', tracking=True)
    customer_short_name = fields.Char(string='Customer Short Name', tracking=True)
    customer_id = fields.Char(string='Customer ID', readonly=True, copy=False)
    customer_email = fields.Char(string='Customer Email', tracking=True)
    contact_person = fields.Char(string='Contact Person')
    contact_number = fields.Char(string='Contact Number')
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        tracking=True,
        help='WhatsApp number synchronized with CRM and the linked Contact.',
    )
    title = fields.Char(string='Title')

    address_street = fields.Char(string='Customer Billing Address')
    address_city = fields.Char(string='City')
    address_state = fields.Many2one('res.country.state', string='State')
    address_country = fields.Many2one('res.country', string='Country')
    postal_code = fields.Char(string='Postal Code')
    business_licence = fields.Char(string='Business Licence')
    vat_no = fields.Char(string='VAT No.')
    is_saudi_customer = fields.Boolean(
        string='Saudi Customer',
        compute='_compute_is_saudi_customer',
        store=True,
    )

    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
        compute='_compute_payment_term_id',
        inverse='_inverse_payment_term_id',
        readonly=False,
        help=(
            'Payment term selected from Odoo accounting payment terms. '
            'Stored in legacy payment_terms column to avoid database upgrade issues.'
        ),
    )
    payment_terms = fields.Char(
        string='Payment Terms Storage',
        help='Stores selected payment term id as text. Old values are kept for compatibility.',
    )
    local_export = fields.Selection([
        ('local', 'Local'),
        ('export', 'Export'),
    ], string='Local/Export Customer', tracking=True)
    contract_type = fields.Selection([
        ('simple_sale', 'Simple Sale'),
        ('long_term_supply', 'Long Term Supply'),
    ], string='Contract Type')
    contract_duration = fields.Integer(
        string='Contract Duration (Months)',
        help='Required only for Long Term Supply contracts.',
    )
    delivery_terms = fields.Selection([
        ('exw', 'EXW - Ex Works'),
        ('fca', 'FCA - Free Carrier'),
        ('fas', 'FAS - Free Alongside Ship'),
        ('fob', 'FOB - Free On Board'),
        ('cfr', 'CFR - Cost and Freight'),
        ('cif', 'CIF - Cost, Insurance and Freight'),
        ('cpt', 'CPT - Carriage Paid To'),
        ('cip', 'CIP - Carriage and Insurance Paid To'),
        ('dap', 'DAP - Delivered At Place'),
        ('dpu', 'DPU - Delivered at Place Unloaded'),
        ('ddp', 'DDP - Delivered Duty Paid'),
    ], string='Delivery Terms')
    port = fields.Char(string='Port (if applicable)')

    new_job = fields.Boolean(string='New Job', default=True)
    repeat_job = fields.Boolean(string='Repeat Job')
    previous_requirement_id = fields.Many2one(
        'crm.requirement.form',
        string='Previous Req Form',
        copy=False,
        index=True,
        help=(
            'For a Repeat Job, select any previous REQ ID that already has '
            'product specifications. Its specifications are copied into this '
            'form for editing.'
        ),
    )
    specification_ids = fields.One2many(
        'crm.requirement.specification',
        'form_id',
        string='Product Specifications',
    )
    next_design_number = fields.Integer(
        string='Next Design Number',
        compute='_compute_next_design_number',
    )
    requirement_details = fields.Text(string='Requirement Details')

    document_attachment_ids = fields.Many2many(
        'ir.attachment',
        'crm_requirement_form_document_attachment_rel',
        'form_id',
        'attachment_id',
        string='Documents',
        copy=False,
        help='Multiple documents submitted by Saudi customers.',
    )

    from_crm = fields.Boolean(string='From CRM', default=False)
    token = fields.Char(string='Token', readonly=True, copy=False)
    public_url = fields.Char(string='Public URL', compute='_compute_public_url', store=True)
    internal_requirement_form = fields.Html(
        string='Internal Requirement Form',
        compute='_compute_internal_requirement_form',
        sanitize=False,
        help=(
            'Embeds the same Requirement Form used by the customer link inside '
            'the Odoo backend Product Specification tab.'
        ),
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('submitted', 'Submitted'),
    ], default='draft', tracking=True)

    customer_rating_count = fields.Integer(
        string='Customer Ranking',
        compute='_compute_customer_rating_count',
    )
    feasibility_yes = fields.Boolean(
        string='YES',
        tracking=True,
    )
    feasibility_cancel = fields.Boolean(
        string='CANCEL',
        tracking=True,
    )
    quotation_count = fields.Integer(
        string='Quotations',
        compute='_compute_quotation_count',
    )

    job_code_count = fields.Integer(
        string='Job Codes',
        compute='_compute_production_references',
    )
    gdn_count = fields.Integer(
        string='GDN Numbers',
        compute='_compute_production_references',
    )
    job_code_links = fields.Html(
        string='Job Code',
        compute='_compute_production_references',
        sanitize=False,
    )
    gdn_number_links = fields.Html(
        string='GDN Number',
        compute='_compute_production_references',
        sanitize=False,
    )


    @api.constrains('feasibility_yes', 'feasibility_cancel')
    def _check_feasibility_choice(self):
        for rec in self:
            if rec.feasibility_yes and rec.feasibility_cancel:
                raise ValidationError(
                    _('Feasibility Check cannot be both YES and CANCEL.')
                )

    @api.onchange('feasibility_yes')
    def _onchange_feasibility_yes(self):
        for rec in self:
            if rec.feasibility_yes:
                rec.feasibility_cancel = False

    @api.onchange('feasibility_cancel')
    def _onchange_feasibility_cancel(self):
        for rec in self:
            if rec.feasibility_cancel:
                rec.feasibility_yes = False

    @api.constrains('new_job', 'repeat_job')
    def _check_job_type_choice(self):
        for rec in self:
            if rec.new_job and rec.repeat_job:
                raise ValidationError(
                    _('Please select only one job type: New Job or Repeat Job.')
                )

    @api.onchange('new_job')
    def _onchange_new_job(self):
        for rec in self:
            if rec.new_job:
                rec.repeat_job = False
                rec.previous_requirement_id = False
                for specification in rec.specification_ids:
                    specification.previous_req_form = False

    @api.onchange('repeat_job')
    def _onchange_repeat_job(self):
        for rec in self:
            if rec.repeat_job:
                rec.new_job = False
            else:
                rec.previous_requirement_id = False

    def _prepare_repeat_specification_values(
        self, specification, sequence, previous_requirement=None
    ):
        self.ensure_one()
        previous_requirement = (
            previous_requirement or self.previous_requirement_id
        )
        simple_fields = [
            'design_name',
            'design_dimension_uom',
            'color_reference',
            'color_reference_type',
            'no_of_colors',
            'quantity',
            'quantity_uom',
            'fg_type',
            'roll_type',
            'bag_type',
            'length',
            'width',
            'gusset',
            'coil_width_mm',
            'cutoff_length_mm',
            'final_roll_direction',
            'final_roll_weight_kg',
            'final_roll_od_mm',
            'final_roll_meters',
            'core_id_mm',
            'core_thickness_mm',
            'core_type',
            'material',
            'thickness',
            'weight',
            'print_finish',
            'standard_features',
            'valve',
            'valve_type',
            'feature_tear_notch_zipper',
            'feature_rounded_corners',
            'feature_other_note',
            'back_if_yes',
            'additional_requirements',
        ]
        values = {
            field_name: specification[field_name]
            for field_name in simple_fields
        }
        values.update({
            'sequence': sequence,
            'no_designs': sequence,
            # Repeat-job specifications are copied as reference designs.
            # Only QTY and UOM remain editable in the specification view.
            'is_duplicate_copy': True,
            'previous_req_form': previous_requirement.name or False,
            'source_specification_id': specification.id or False,
            'quantity_uom_id': specification.quantity_uom_id.id or False,
            'bag_type_id': specification.bag_type_id.id or False,
            'bag_type_product_tmpl_id': (
                specification.bag_type_product_tmpl_id.id or False
            ),
            'print_type_id': specification.print_type_id.id or False,
            'print_finish_id': specification.print_finish_id.id or False,
            'print_finish_ids': [
                (6, 0, specification.print_finish_ids.ids)
            ],
            'standard_feature_ids': [
                (6, 0, specification.standard_feature_ids.ids)
            ],
        })
        highest_layer = 1
        for layer_no in range(1, 11):
            product_tmpl = specification[
                f'layer_{layer_no}_product_tmpl_id'
            ]
            variant = specification[f'layer_{layer_no}_variant_id']
            material_name = specification[f'layer_{layer_no}_material']

            # Older/synced requirement records can retain the layer material
            # snapshot while the product-template relation is empty.  Resolve
            # the relation before creating the repeat-job copy so the layer
            # never turns into an "Unnamed" product in the new form.
            if not product_tmpl and material_name:
                product_tmpl = self.env['product.template'].search([
                    ('name', '=', material_name),
                ], limit=1)
                if not product_tmpl:
                    product_tmpl = self.env['product.template'].search([
                        ('name', 'ilike', material_name),
                    ], limit=1)
            if product_tmpl and variant and variant.product_tmpl_id != product_tmpl:
                variant = self.env['product.product']
            if product_tmpl and not variant and len(product_tmpl.product_variant_ids) == 1:
                variant = product_tmpl.product_variant_ids[:1]

            if product_tmpl or material_name:
                highest_layer = layer_no
            values.update({
                f'layer_{layer_no}_product_tmpl_id': product_tmpl.id or False,
                f'layer_{layer_no}_variant_id': variant.id or False,
                f'layer_{layer_no}_material': (
                    material_name
                    or product_tmpl.display_name
                    or False
                ),
                f'layer_{layer_no}_thickness': (
                    specification[f'layer_{layer_no}_thickness'] or 0.0
                ),
            })
        # Show every populated layer card immediately (before the first
        # save) instead of only Layer 1.
        values['layer_visible_count'] = highest_layer
        return values

    def _repeat_specification_commands(self, previous_requirement):
        self.ensure_one()
        commands = [Command.clear()]
        for sequence, specification in enumerate(
            previous_requirement.specification_ids.sorted(
                key=lambda line: (line.sequence, line.id)
            ),
            start=1,
        ):
            commands.append(Command.create(
                self._prepare_repeat_specification_values(
                    specification,
                    sequence,
                    previous_requirement=previous_requirement,
                )
            ))
        return commands

    @api.onchange('previous_requirement_id')
    def _onchange_previous_requirement_id(self):
        for rec in self:
            previous = rec.previous_requirement_id
            if not previous:
                continue
            if previous == rec._origin:
                rec.previous_requirement_id = False
                return {
                    'warning': {
                        'title': _('Invalid Previous Requirement'),
                        'message': _(
                            'The current Requirement Form cannot be used as its '
                            'own previous requirement.'
                        ),
                    }
                }
            if not previous.specification_ids:
                rec.previous_requirement_id = False
                return {
                    'warning': {
                        'title': _('No Product Specifications'),
                        'message': _(
                            'The selected Requirement Form has no Product '
                            'Specifications to copy.'
                        ),
                    }
                }

            rec.repeat_job = True
            rec.new_job = False
            # Populate the current form immediately in the web client.  Using
            # explicit Command objects in onchange makes the One2many rows
            # virtual/editable straight away; the user does not need to save
            # the Requirement Form before opening the fetched specifications.
            rec.update({
                'specification_ids': rec._repeat_specification_commands(previous),
            })

    @api.depends('specification_ids')
    def _compute_next_design_number(self):
        for rec in self:
            rec.next_design_number = len(rec.specification_ids) + 1

    @api.onchange('specification_ids')
    def _onchange_specification_ids_numbering(self):
        for rec in self:
            for design_no, specification in enumerate(
                rec.specification_ids, start=1
            ):
                specification.sequence = design_no
                specification.no_designs = design_no

    def _compute_production_references(self):
        """Expose Job Code and GDN references directly from the REQ record."""
        for rec in self:
            rec.job_code_count = 0
            rec.gdn_count = 0
            rec.job_code_links = False
            rec.gdn_number_links = False

        persisted = self.filtered(lambda rec: isinstance(rec.id, int))
        if not persisted:
            return

        lines = self.env['sale.order.line'].search([
            ('order_id.requirement_form_id', 'in', persisted.ids),
            ('display_type', '=', False),
        ], order='order_id, sequence, id')

        grouped = {rec.id: [] for rec in persisted}
        for line in lines:
            requirement = line.order_id.requirement_form_id
            if requirement and requirement.id in grouped:
                grouped[requirement.id].append(line)

        for rec in persisted:
            job_links = []
            gdn_links = []
            seen_job_lines = set()
            seen_gdns = set()

            for line in grouped.get(rec.id, []):
                if line.job_code and line.id not in seen_job_lines:
                    seen_job_lines.add(line.id)
                    job_links.append(
                        Markup(
                            '<a class="o_crm_req_reference_link" '
                            'href="/web#id={}&amp;model=sale.job.code.configuration'
                            '&amp;view_type=form">{}</a>'
                        ).format(line.id, escape(line.job_code))
                    )

                configuration = line.gdn_configuration_id
                if (
                    line.gdn_number
                    and configuration
                    and configuration.id not in seen_gdns
                ):
                    seen_gdns.add(configuration.id)
                    gdn_links.append(
                        Markup(
                            '<a class="o_crm_req_reference_link" '
                            'href="/web#id={}&amp;model=sale.gdn.configuration'
                            '&amp;view_type=form">{}</a>'
                        ).format(configuration.id, escape(line.gdn_number))
                    )

            rec.job_code_count = len(job_links)
            rec.gdn_count = len(gdn_links)
            rec.job_code_links = Markup(' ').join(job_links) if job_links else False
            rec.gdn_number_links = Markup(' ').join(gdn_links) if gdn_links else False

    def action_open_job_codes(self):
        self.ensure_one()
        domain = [('requirement_form_id', '=', self.id)]
        records = self.env['sale.job.code.configuration'].search(domain)
        if not records:
            raise UserError(_('No Job Code has been generated for this REQ ID yet.'))
        if len(records) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Job Code'),
                'res_model': 'sale.job.code.configuration',
                'view_mode': 'form',
                'res_id': records.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Codes'),
            'res_model': 'sale.job.code.configuration',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    def action_open_gdn_configurations(self):
        self.ensure_one()
        domain = [('requirement_form_id', '=', self.id)]
        records = self.env['sale.gdn.configuration'].search(domain)
        if not records:
            raise UserError(_('No GDN has been generated for this REQ ID yet.'))
        if len(records) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('GDN Number'),
                'res_model': 'sale.gdn.configuration',
                'view_mode': 'form',
                'res_id': records.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('GDN Numbers'),
            'res_model': 'sale.gdn.configuration',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    @api.depends('lead_id', 'partner_id')
    def _compute_quotation_count(self):
        grouped_data = self.env['sale.order'].read_group(
            [('requirement_form_id', 'in', self.ids)],
            ['requirement_form_id'],
            ['requirement_form_id'],
        )
        count_by_form = {
            item['requirement_form_id'][0]: item['requirement_form_id_count']
            for item in grouped_data
        }
        for rec in self:
            rec.quotation_count = count_by_form.get(rec.id, 0)

    def _prepare_sale_order_line_from_specification(self, specification):
        bag_type_variant = specification.bag_type_product_tmpl_id.product_variant_ids.filtered(
            lambda product: product.active
        )[:1]
        values = {
            'requirement_specification_id': specification.id,
            'product_id': bag_type_variant.id or False,
            'name': specification.design_name or _('Design %s') % specification.no_designs,
            'req_design_name': specification.design_name or '',
            'req_design_dimension_uom': specification.design_dimension_uom or 'mm',
            'req_design_no': specification.no_designs or specification.sequence or 1,
            'req_color_reference': specification.color_reference or False,
            'req_color_reference_type': specification.color_reference_type or False,
            'req_print_type_id': specification.print_type_id.id or False,
            'req_no_of_colors': specification.no_of_colors or 0,
            'req_quantity': specification.quantity,
            'req_quantity_uom': specification.quantity_uom or False,
            'req_quantity_uom_id': specification.quantity_uom_id.id or False,
            'product_uom_qty': specification.quantity,
            'req_fg_type': specification.fg_type or 'bag',
            'req_roll_type': specification.roll_type or False,
            'req_bag_type_product_tmpl_id': (
                specification.bag_type_product_tmpl_id.id or False
            ),
            'req_length': specification.length,
            'req_width': specification.width,
            'req_gusset': specification.gusset,
            'req_coil_width_mm': specification.coil_width_mm,
            'req_cutoff_length_mm': specification.cutoff_length_mm,
            'req_final_roll_direction': specification.final_roll_direction or False,
            'req_final_roll_weight_kg': specification.final_roll_weight_kg,
            'req_final_roll_od_mm': specification.final_roll_od_mm,
            'req_final_roll_meters': specification.final_roll_meters,
            'req_core_id_mm': specification.core_id_mm,
            'req_core_thickness_mm': specification.core_thickness_mm,
            'req_core_type': specification.core_type or False,
            'req_total_thickness': specification.total_thickness,
            'req_print_finish_id': specification.print_finish_id.id or False,
            'req_print_finish_ids': [(6, 0, specification.print_finish_id.ids)],
            'req_feature_ids': [(6, 0, specification.standard_feature_ids.ids)],
            'req_additional_requirements': specification.additional_requirements or False,
        }
        # Repeat jobs reuse only the exact source design's GDN, even when
        # the new quotation belongs to a different customer.
        source = specification.source_specification_id
        if self.repeat_job and source:
            source_lines = source.sale_order_line_ids.filtered(
                lambda line: not line.display_type
                and line.gdn_configuration_id
            ).sorted(key=lambda line: (line.order_id.id, line.id), reverse=True)
            if source_lines:
                configuration = source_lines[0].gdn_configuration_id
                values['gdn_configuration_id'] = configuration.id
                values['gdn_number'] = configuration.gdn_number
        for layer_no in range(1, 11):
            template = specification[f'layer_{layer_no}_product_tmpl_id']
            variant = specification[f'layer_{layer_no}_variant_id']
            values[f'req_layer_{layer_no}_product_tmpl_id'] = template.id or False
            values[f'req_layer_{layer_no}_variant_id'] = variant.id or False
        return values

    def _sync_specifications_to_sale_order(self, order):
        self.ensure_one()
        existing_lines = {
            line.requirement_specification_id.id: line
            for line in order.order_line
            if line.requirement_specification_id
        }
        for specification in self.specification_ids.sorted(
            key=lambda line: (line.sequence, line.id)
        ):
            values = self._prepare_sale_order_line_from_specification(specification)
            existing_line = existing_lines.get(specification.id)
            if existing_line:
                # Never replace a GDN already assigned to this quotation line.
                if existing_line.gdn_configuration_id or existing_line.gdn_number:
                    values.pop('gdn_configuration_id', None)
                    values.pop('gdn_number', None)
                existing_line.write(values)
            else:
                values['order_id'] = order.id
                self.env['sale.order.line'].create(values)

    def _ensure_sales_customer_code(self):
        """Ensure the Requirement Form customer has a Customer Code.

        Pure vendors do not receive Customer Codes automatically. However, once
        a partner is explicitly used as a customer through a Requirement Form /
        quotation flow, it needs a Customer Code for Job Code and GDN generation.
        """
        self.ensure_one()
        partner = (self.partner_id or self.lead_id.partner_id).commercial_partner_id
        if not partner:
            return False

        customer_code = (partner.customer_code or self.customer_id or '').strip()
        if not customer_code and self.lead_id:
            customer_code = (self.lead_id.generated_customer_id or '').strip()

        if not customer_code:
            country = (
                partner.country_id
                or self.address_country
                or self.lead_id.country_id
            )
            customer_code = partner._ensure_customer_code_for_sales(
                country=country
            )

        if partner.customer_code != customer_code:
            partner.with_context(
                skip_supplier_customer_code_cleanup=True,
                skip_customer_code_country_sync=True,
            ).write({'customer_code': customer_code})

        if self.customer_id != customer_code:
            self.write({'customer_id': customer_code})

        if (
            self.lead_id
            and self.lead_id.generated_customer_id != customer_code
        ):
            self.lead_id.with_context(
                skip_customer_code_partner_sync=True
            ).write({'generated_customer_id': customer_code})

        return customer_code

    def _get_sale_incoterm(self):
        """Return the Sale Order Incoterm matching this form's Delivery Terms."""
        self.ensure_one()
        if not self.delivery_terms:
            return self.env['account.incoterms']
        return self.env['account.incoterms'].search(
            [('code', '=ilike', self.delivery_terms)], limit=1
        )

    def _sync_incoterm_to_sale_orders(self):
        """Delivery Terms -> Incoterm on the form's open quotations."""
        orders = self.env['sale.order'].search([
            ('requirement_form_id', 'in', self.ids),
            ('state', 'in', ('draft', 'sent')),
        ])
        for order in orders:
            incoterm = order.requirement_form_id._get_sale_incoterm()
            if order.incoterm != incoterm:
                order.write({'incoterm': incoterm.id or False})

    def _create_quotation_from_requirement(self):
        self.ensure_one()
        partner = self.partner_id or self.lead_id.partner_id
        if not partner:
            raise UserError(
                _('Please select a Customer before creating the quotation.')
            )

        self._ensure_sales_customer_code()
        values = {
            'partner_id': partner.id,
            'requirement_form_id': self.id,
        }
        if self.payment_term_id:
            values['payment_term_id'] = self.payment_term_id.id
        incoterm = self._get_sale_incoterm()
        if incoterm:
            values['incoterm'] = incoterm.id
        if self.lead_id:
            values['opportunity_id'] = self.lead_id.id
        order = self.env['sale.order'].create(values)
        self._sync_specifications_to_sale_order(order)
        return order

    def action_open_quotations(self):
        self.ensure_one()
        if not self.feasibility_yes:
            raise UserError(
                _('Feasibility Check must be YES before opening a quotation.')
            )
        if not self.specification_ids:
            raise UserError(
                _('Please add at least one Product Specification first.')
            )

        if not (self.partner_id or self.lead_id.partner_id):
            raise UserError(_('Please select a Customer first.'))

        self._ensure_sales_customer_code()
        domain = [('requirement_form_id', '=', self.id)]
        orders = self.env['sale.order'].search(domain)
        if orders and self.payment_term_id:
            orders.filtered(
                lambda order: order.payment_term_id != self.payment_term_id
            ).write({'payment_term_id': self.payment_term_id.id})
        if orders:
            orders.filtered(
                lambda order: order.state in ('draft', 'sent')
            ).mapped('requirement_form_id')._sync_incoterm_to_sale_orders()
        if not orders:
            order = self._create_quotation_from_requirement()
            if self.lead_id:
                self.lead_id._refresh_requirement_summary()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Quotation'),
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': order.id,
                'target': 'current',
            }

        # The Product Specifications are native Odoo fields now. Whenever the
        # Quotation smart button is used, push the latest saved specification
        # values to all existing linked quotations before opening them.
        for linked_order in orders:
            self._sync_specifications_to_sale_order(linked_order)
        if self.lead_id:
            self.lead_id._refresh_requirement_summary()

        if len(orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Quotation'),
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': orders.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotations'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_opportunity_id': self.lead_id.id,
            },
        }

    def _requirement_audit_excluded_fields(self):
        """Technical fields that should never create chatter noise."""
        return {
            'message_ids',
            'message_follower_ids',
            'message_partner_ids',
            'message_main_attachment_id',
            'activity_ids',
            'activity_state',
            'activity_type_id',
            'activity_user_id',
            'activity_date_deadline',
            'create_uid',
            'create_date',
            'write_uid',
            'write_date',
            'internal_requirement_form',
            'public_url',
            'next_design_number',
            'customer_rating_count',
            'quotation_count',
            'job_code_count',
            'gdn_count',
            'job_code_links',
            'gdn_number_links',
            'specification_ids',
        }

    def _requirement_audit_value(self, field_name):
        """Return a safe, readable representation of a field value."""
        self.ensure_one()
        field = self._fields.get(field_name)
        if not field:
            return ''
        value = self[field_name]
        field_type = field.type

        if field_type == 'many2one':
            return value.display_name if value else ''
        if field_type in ('one2many', 'many2many'):
            if not value:
                return ''
            return ', '.join(value.mapped('display_name'))
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

    def _post_requirement_audit(self, title, rows=None):
        """Post field changes in a native-style, line-by-line chatter format."""
        rows = rows or []
        for rec in self:
            body = Markup('<p class="mb-1"><strong>{}</strong></p>').format(
                escape(title)
            )
            for label, before, after in rows:
                safe_label = escape(label or '')
                safe_before = escape(before or '')
                safe_after = escape(after or '')

                # For creation entries there is no meaningful "before" value.
                # Keep those compact, while updates use the familiar Odoo-style
                # old-value → new-value line.
                if not before and after:
                    body += Markup(
                        '<div class="o_mail_tracking_value mb-1">'
                        '<span class="fw-bold">{}</span>: {}'
                        '</div>'
                    ).format(safe_label, safe_after)
                else:
                    body += Markup(
                        '<div class="o_mail_tracking_value mb-1">'
                        '<span class="fw-bold">{}</span>: {} '
                        '<span class="text-muted">→</span> {}'
                        '</div>'
                    ).format(
                        safe_label,
                        safe_before or Markup('<span class="text-muted">—</span>'),
                        safe_after or Markup('<span class="text-muted">—</span>'),
                    )

            rec.with_context(skip_requirement_audit=True).message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def write(self, vals):
        if self.env.context.get('skip_requirement_audit'):
            return super().write(vals)

        vals = dict(vals)
        previous_id = vals.get('previous_requirement_id')
        if previous_id and 'specification_ids' not in vals:
            previous = self.env['crm.requirement.form'].browse(
                previous_id
            ).exists()
            if previous and previous.specification_ids:
                # Persist the exact selected previous REQ even if the web
                # client only sent the Many2one change. This complements the
                # onchange instant preview and makes the fetched lines survive
                # Save/Save & Close reliably.
                vals['repeat_job'] = True
                vals['new_job'] = False
                vals['specification_ids'] = (
                    self[:1]._repeat_specification_commands(previous)
                )

        excluded = self._requirement_audit_excluded_fields()
        audit_fields = []
        for field_name in vals:
            field = self._fields.get(field_name)
            if not field or field_name in excluded:
                continue
            # Native mail.thread already gives a proper before/after entry for
            # fields marked tracking=True. Do not duplicate those messages.
            if getattr(field, 'tracking', False):
                continue
            audit_fields.append(field_name)

        before_by_record = {
            rec.id: {
                field_name: rec._requirement_audit_value(field_name)
                for field_name in audit_fields
            }
            for rec in self
        }

        old_leads = self.mapped('lead_id')
        result = super().write(vals)
        summary_leads = old_leads | self.mapped('lead_id')
        if summary_leads:
            summary_leads._refresh_requirement_summary()

        if (
            'whatsapp_number' in vals
            and not self.env.context.get('skip_whatsapp_partner_sync')
        ):
            for rec in self:
                if rec.partner_id:
                    if rec.partner_id.whatsapp_number != rec.whatsapp_number:
                        rec.partner_id.with_context(
                            skip_whatsapp_related_sync=True,
                        ).write({
                            'whatsapp_number': rec.whatsapp_number or False,
                        })
                elif rec.lead_id and rec.lead_id.whatsapp_number != rec.whatsapp_number:
                    rec.lead_id.with_context(
                        skip_whatsapp_partner_sync=True,
                    ).write({
                        'whatsapp_number': rec.whatsapp_number or False,
                    })

        if 'delivery_terms' in vals:
            self._sync_incoterm_to_sale_orders()

        if (
            'customer_short_name' in vals
            and not self.env.context.get('skip_short_name_partner_sync')
        ):
            for rec in self:
                name = (rec.customer_short_name or '').strip()
                if not name:
                    continue
                lead = rec.lead_id
                partner = (rec.partner_id or lead.partner_id).commercial_partner_id
                if partner:
                    if partner.ref != name:
                        # Partner write aligns its CRM records and all forms.
                        partner.write({'ref': name})
                elif lead and lead.customer_short_name != name:
                    # Lead write aligns the Contact (if any) and its forms.
                    lead.write({'customer_short_name': name})

        if (
            'vat_no' in vals
            and not self.env.context.get('skip_vat_partner_sync')
        ):
            for rec in self:
                vat = (rec.vat_no or '').strip() or False
                lead = rec.lead_id
                partner = (rec.partner_id or lead.partner_id).commercial_partner_id
                if partner:
                    if (partner.vat or False) != vat:
                        partner.with_context(skip_vat_related_sync=True).write({
                            'vat': vat,
                        })
                    # Aligns the Contact's CRM records and all its forms.
                    partner._sync_vat_to_related_records()
                elif lead:
                    if (lead.vat_no or False) != vat:
                        lead.with_context(skip_vat_partner_sync=True).write({
                            'vat_no': vat,
                        })
                    lead._sync_vat_with_partner(prefer_lead=True)

        for rec in self:
            rows = []
            before_values = before_by_record.get(rec.id, {})
            for field_name in audit_fields:
                before = before_values.get(field_name, '')
                after = rec._requirement_audit_value(field_name)
                if before == after:
                    continue
                field = rec._fields[field_name]
                rows.append((field.string or field_name, before, after))
            if rows:
                rec._post_requirement_audit(
                    _('Requirement Form updated'), rows
                )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            previous_id = vals.get('previous_requirement_id')
            if previous_id and not vals.get('specification_ids'):
                previous = self.env['crm.requirement.form'].browse(
                    previous_id
                ).exists()
                if previous and previous.specification_ids:
                    virtual = self.new({
                        'previous_requirement_id': previous.id,
                        'repeat_job': True,
                        'new_job': False,
                    })
                    vals['repeat_job'] = True
                    vals['new_job'] = False
                    vals['specification_ids'] = (
                        virtual._repeat_specification_commands(previous)
                    )
            if vals.get('lead_id') and not vals.get('customer_id'):
                lead = self.env['crm.lead'].browse(vals['lead_id']).exists()
                if lead:
                    if not lead.generated_customer_id:
                        country = lead.country_id or lead.partner_id.country_id
                        lead.generated_customer_id = lead._generate_customer_id(
                            country=country
                        )
                    vals['customer_id'] = lead.generated_customer_id
            elif vals.get('partner_id') and not vals.get('lead_id'):
                partner = self.env['res.partner'].browse(vals['partner_id']).exists()
                if partner:
                    prepared_values = self.env['crm.requirement.form'].new({
                        'partner_id': partner.id,
                    })._prepare_requirement_values_from_partner(partner)
                    for field_name, value in prepared_values.items():
                        if field_name in vals or field_name == 'partner_id':
                            continue
                        vals[field_name] = value

            if not vals.get('customer_short_name'):
                ref_partner = (
                    self.env['res.partner'].browse(vals['partner_id']).exists()
                    if vals.get('partner_id') else self.env['res.partner']
                )
                ref_lead = (
                    self.env['crm.lead'].browse(vals['lead_id']).exists()
                    if vals.get('lead_id') else self.env['crm.lead']
                )
                fetched_name = (
                    ref_partner.commercial_partner_id.ref
                    or ref_lead.partner_id.commercial_partner_id.ref
                    or ref_lead.customer_short_name
                )
                if fetched_name:
                    vals['customer_short_name'] = fetched_name

            if not vals.get('vat_no'):
                vat_partner = (
                    self.env['res.partner'].browse(vals['partner_id']).exists()
                    if vals.get('partner_id') else self.env['res.partner']
                )
                vat_lead = (
                    self.env['crm.lead'].browse(vals['lead_id']).exists()
                    if vals.get('lead_id') else self.env['crm.lead']
                )
                fetched_vat = (
                    vat_partner.commercial_partner_id.vat
                    or vat_lead.partner_id.commercial_partner_id.vat
                    or vat_lead.vat_no
                )
                if fetched_vat:
                    vals['vat_no'] = fetched_vat

            if vals.get('name') in (False, None, '', 'New', 'Requirement Form'):
                vals['name'] = self._generate_requirement_reference(vals)
        records = super().create(vals_list)
        leads = records.mapped('lead_id')
        if leads:
            leads._refresh_requirement_summary()
        for record in records:
            record._post_requirement_audit(_('Requirement Form created'))
        return records

    @api.model
    def _sanitize_customer_short_name(self, value):
        short_name = re.sub(r'[^A-Za-z0-9]+', '', value or '').upper()
        return short_name[:12] or 'CUST'

    @api.model
    def _generate_requirement_reference(self, vals):
        date_part = fields.Date.context_today(self).strftime('%d%m%y')
        short_name = vals.get('customer_short_name')

        if not short_name and vals.get('lead_id'):
            lead = self.env['crm.lead'].browse(vals['lead_id'])
            short_name = lead.customer_short_name or lead.partner_id.ref
        if not short_name and vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            short_name = partner.ref or partner.name
        if not short_name:
            short_name = vals.get('customer_name')

        customer_code = self._sanitize_customer_short_name(short_name)
        prefix = f'REQ_{date_part}_{customer_code}_'
        next_serial = self.search_count([('name', '=like', f'{prefix}%')]) + 1
        return f'{prefix}{next_serial:02d}'

    @api.depends('state')
    def _compute_internal_requirement_form(self):
        for rec in self:
            if not rec.id:
                rec.internal_requirement_form = (
                    '<div class="alert alert-info mb-0">'
                    'Save the Requirement Form once to load Product Specification.'
                    '</div>'
                )
                continue

            internal_url = f'/requirement/form/internal/{rec.id}'
            rec.internal_requirement_form = (
                '<div style="width:100%;height:calc(100vh - 235px);'
                'min-height:850px;border:1px solid #dee2e6;border-radius:8px;'
                'overflow:hidden;background:#fff;">'
                f'<iframe src="{internal_url}" '
                'style="width:100%;height:100%;border:0;display:block;" '
                'loading="eager" referrerpolicy="same-origin"></iframe>'
                '</div>'
            )

    @api.depends('token')
    def _compute_public_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.public_url = f'{base_url}/requirement/form/{rec.token}' if rec.token else False

    @api.onchange('address_country')
    def _onchange_address_country_default_local_export(self):
        for rec in self:
            if rec.address_country and not rec.local_export:
                rec.local_export = (
                    'local'
                    if rec.address_country.name == 'Saudi Arabia'
                    else 'export'
                )

    @api.depends('address_country')
    def _compute_is_saudi_customer(self):
        for rec in self:
            rec.is_saudi_customer = bool(
                rec.address_country and rec.address_country.name == 'Saudi Arabia'
            )

    @api.depends('payment_terms')
    def _compute_payment_term_id(self):
        PaymentTerm = self.env['account.payment.term']
        for rec in self:
            payment_term = False
            stored_value = (rec.payment_terms or '').strip()
            if stored_value.isdigit():
                payment_term = PaymentTerm.browse(int(stored_value)).exists()
            rec.payment_term_id = payment_term

    def _inverse_payment_term_id(self):
        for rec in self:
            rec.payment_terms = (
                str(rec.payment_term_id.id) if rec.payment_term_id else False
            )

    def _get_payment_terms_display(self):
        self.ensure_one()
        legacy_labels = {
            '50_50': '50% Advance, 50% Remaining before shipping + Shipping',
            'other': 'Other',
        }
        return (
            self.payment_term_id.name
            or legacy_labels.get(self.payment_terms or '', self.payment_terms or '')
        )

    def _prepare_requirement_values_from_partner(self, partner):
        self.ensure_one()
        partner = partner.exists()
        if not partner:
            return {}

        invoice_partner = partner.child_ids.filtered(
            lambda child: child.type == 'invoice'
        )[:1]
        billing_partner = invoice_partner or partner

        country = billing_partner.country_id or partner.country_id
        state = billing_partner.state_id or partner.state_id
        customer_short_name = partner.ref or self._sanitize_customer_short_name(
            partner.name
        )

        business_licence = ''
        if 'business_licence' in partner._fields:
            business_licence = partner.business_licence or ''

        payment_term_value = False
        if (
            'property_payment_term_id' in partner._fields
            and partner.property_payment_term_id
        ):
            payment_term_value = str(partner.property_payment_term_id.id)

        return {
            'partner_id': partner.id,
            'customer_name': partner.name or '',
            'customer_short_name': customer_short_name,
            'customer_id': partner.customer_code or '',
            'customer_email': partner.email or '',
            'contact_person': partner.name or '',
            'contact_number': partner.phone or getattr(partner, 'mobile', False) or '',
            'whatsapp_number': partner.whatsapp_number or '',
            'title': partner.function or '',
            'address_street': billing_partner.street or partner.street or '',
            'address_city': billing_partner.city or partner.city or '',
            'address_state': state.id if state else False,
            'address_country': country.id if country else False,
            'postal_code': billing_partner.zip or partner.zip or '',
            'business_licence': business_licence,
            'vat_no': partner.commercial_partner_id.vat or '',
            'local_export': (
                'local'
                if country and (country.code == 'SA' or country.name == 'Saudi Arabia')
                else 'export'
            ) if country else False,
            'payment_terms': payment_term_value,
        }

    def _apply_customer_values(self, values, skip_fields=None):
        skip_fields = set(skip_fields or [])
        for field_name, value in values.items():
            if field_name in self._fields and field_name not in skip_fields:
                self[field_name] = value

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        for rec in self:
            if not rec.lead_id:
                continue
            values = rec.lead_id._get_requirement_customer_values()
            rec._apply_customer_values(values, skip_fields={'lead_id', 'from_crm'})

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            if rec.from_crm or rec.lead_id or not rec.partner_id:
                continue
            values = rec._prepare_requirement_values_from_partner(rec.partner_id)
            rec._apply_customer_values(values, skip_fields={'partner_id'})

    @api.depends('lead_id', 'partner_id')
    def _compute_customer_rating_count(self):
        lead_ids = self.mapped('lead_id').ids
        partner_ids = self.filtered(lambda rec: not rec.lead_id).mapped(
            'partner_id'
        ).ids

        count_by_lead = {}
        if lead_ids:
            grouped_by_lead = self.env['crm.customer.rating'].read_group(
                [('lead_id', 'in', lead_ids)],
                ['lead_id'],
                ['lead_id'],
            )
            count_by_lead = {
                item['lead_id'][0]: item['lead_id_count']
                for item in grouped_by_lead
            }

        count_by_partner = {}
        if partner_ids:
            grouped_by_partner = self.env['crm.customer.rating'].read_group(
                [('partner_id', 'in', partner_ids)],
                ['partner_id'],
                ['partner_id'],
            )
            count_by_partner = {
                item['partner_id'][0]: item['partner_id_count']
                for item in grouped_by_partner
            }

        for rec in self:
            if rec.lead_id:
                rec.customer_rating_count = count_by_lead.get(rec.lead_id.id, 0)
            elif rec.partner_id:
                rec.customer_rating_count = count_by_partner.get(
                    rec.partner_id.id, 0
                )
            else:
                rec.customer_rating_count = 0

    def action_open_customer_rating(self):
        self.ensure_one()
        if self.lead_id:
            rating = self.env['crm.customer.rating'].search([
                ('lead_id', '=', self.lead_id.id),
            ], limit=1)
            if not rating:
                rating = self.env['crm.customer.rating'].create({
                    'lead_id': self.lead_id.id,
                })
            return {
                'type': 'ir.actions.act_window',
                'name': _('Customer Ranking'),
                'res_model': 'crm.customer.rating',
                'view_mode': 'form',
                'res_id': rating.id,
                'target': 'current',
            }

        if not self.partner_id:
            raise UserError(_('Please select a Customer first.'))

        ratings = self.env['crm.customer.rating'].search([
            ('partner_id', '=', self.partner_id.id),
        ])
        if len(ratings) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Customer Ranking'),
                'res_model': 'crm.customer.rating',
                'view_mode': 'form',
                'res_id': ratings.id,
                'target': 'current',
            }
        if ratings:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Customer Rankings'),
                'res_model': 'crm.customer.rating',
                'view_mode': 'list,form',
                'domain': [('partner_id', '=', self.partner_id.id)],
                'target': 'current',
            }

        raise UserError(
            _(
                'No Customer Ranking exists for this customer yet. '
                'Create the ranking from one of the customer CRM leads first.'
            )
        )

    def _validate_internal_requirement(self):
        for rec in self:
            if not rec.new_job and not rec.repeat_job:
                raise ValidationError(
                    _('Please select either New Job or Repeat Job.')
                )
            if not rec.specification_ids:
                raise ValidationError(
                    _('Please add at least one Product Specification.')
                )
            if rec.repeat_job and not (
                rec.previous_requirement_id
                or any(rec.specification_ids.mapped('previous_req_form'))
            ):
                raise ValidationError(
                    _('Please select a Previous Req Form for a Repeat Job.')
                )

            for specification in rec.specification_ids:
                design_label = specification.design_name or _(
                    'Design %s'
                ) % (specification.no_designs or specification.sequence or 1)
                missing = []
                if not specification.design_name:
                    missing.append(_('Design Name'))
                if not specification.design_dimension_uom:
                    missing.append(_('Design Dimension UOM'))
                if not specification.color_reference:
                    missing.append(_('Color Reference'))
                if (
                    specification.color_reference == 'yes'
                    and not specification.color_reference_type
                ):
                    missing.append(_('Color Reference Type'))
                if not specification.quantity_uom_id:
                    missing.append(_('UOM'))
                if not specification.fg_type:
                    missing.append(_('FG Type'))
                if not specification.bag_type_product_tmpl_id:
                    missing.append(_('Product'))
                if not specification.print_finish_id:
                    missing.append(_('Print and Finish'))
                if not specification.layer_1_product_tmpl_id:
                    missing.append(_('Layer 1'))
                if missing:
                    raise ValidationError(
                        _('%(design)s: Please complete %(fields)s.') % {
                            'design': design_label,
                            'fields': ', '.join(missing),
                        }
                    )

    def action_submit_internal(self):
        self.ensure_one()
        self._validate_internal_requirement()
        if self.state != 'submitted':
            self.write({'state': 'submitted'})

        orders = self.env['sale.order'].search([
            ('requirement_form_id', '=', self.id),
        ])
        for order in orders:
            self._sync_specifications_to_sale_order(order)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Requirement Form'),
            'res_model': 'crm.requirement.form',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'crm_requirement_form.crm_requirement_form_form'
            ).id,
            'res_id': self.id,
            'target': 'current',
        }

    def action_reset_internal_to_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})
        return True

    def _ensure_public_customer_link(self):
        self.ensure_one()
        if not self.token:
            self.token = str(uuid.uuid4())
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f'{base_url}/requirement/form/{self.token}'

    def action_generate_customer_link(self):
        self.ensure_one()
        public_url = self._ensure_public_customer_link()
        self._compute_public_url()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Customer Link Generated'),
                'message': _('Use this link in Send to Customer: %s') % public_url,
                'type': 'success',
                'sticky': True,
            },
        }

    def action_send_requirement_form(self):
        self.ensure_one()
        if not self.customer_email:
            raise UserError(_('Please set customer email first.'))
        public_url = self._ensure_public_customer_link()
        self._compute_public_url()

        mail_values = {
            'subject': f'Product Requirement Form – Action Required | {self.name}',
            'email_to': self.customer_email,
            'body_html': f'''
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:30px;
                            border:1px solid #e0e0e0;border-radius:8px;">
                    <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px;">
                        Product Requirement Form
                    </h2>
                    <p>Dear <strong>{self.customer_name or 'Valued Customer'}</strong>,</p>
                    <p>We hope this message finds you well. Please complete the
                    <strong>Product Requirement Form</strong> using the link below.</p>
                    <div style="text-align:center;margin:30px 0;">
                        <a href="{public_url}"
                           style="background-color:#3498db;color:#ffffff;padding:14px 32px;
                                  text-decoration:none;border-radius:5px;font-size:16px;font-weight:bold;">
                            Complete Requirement Form
                        </a>
                    </div>
                    <p style="font-size:13px;color:#7f8c8d;">
                        If the button does not work, copy and paste this link into your browser:<br/>
                        <a href="{public_url}">{public_url}</a>
                    </p>
                    <p>Warm regards,<br/><strong>Sales &amp; Business Development Team</strong></p>
                </div>
            ''',
        }
        self.env['mail.mail'].sudo().create(mail_values).send()
        self.state = 'sent'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Requirement Form Sent Successfully'),
                'message': _('Form sent to: %s') % self.customer_email,
                'type': 'success',
                'sticky': True,
            },
        }

    def action_print_requirement_form(self):
        self.ensure_one()
        return self.env.ref(
            'crm_requirement_form.action_report_requirement_form'
        ).report_action(self)
