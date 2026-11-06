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
    previous_requirement_ids = fields.Many2many(
        'crm.requirement.form',
        'crm_req_form_previous_source_rel',
        'form_id',
        'source_form_id',
        string='Previous Req Forms',
        copy=False,
        help=(
            'Select multiple previous Requirement Forms from the same customer. '
            'Only new source designs are appended; existing designs stay intact.'
        ),
    )
    loaded_previous_requirement_ids = fields.Many2many(
        'crm.requirement.form',
        'crm_req_form_loaded_source_rel',
        'form_id',
        'source_form_id',
        string='Previously Loaded REQs',
        copy=False,
        help='Technical selection snapshot, prevents deleted rows from being re-imported.',
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
                rec.previous_requirement_ids = [Command.clear()]
                rec.loaded_previous_requirement_ids = [Command.clear()]
                for specification in rec.specification_ids:
                    specification.previous_req_form = False

    @api.onchange('repeat_job')
    def _onchange_repeat_job(self):
        for rec in self:
            if rec.repeat_job:
                rec.new_job = False
            else:
                rec.previous_requirement_id = False
                rec.previous_requirement_ids = [Command.clear()]
                rec.loaded_previous_requirement_ids = [Command.clear()]

    def _prepare_repeat_specification_values(
        self, specification, sequence, previous_requirement=None
    ):
        """Take a complete, independent snapshot of one previous design.

        Copy all copyable stored business values, including technical notes,
        dimensions, material variants, selected options and document lines.
        Do not link the new row to the source's parent or its sale lines.
        The separate source_specification_id is traceability only.
        """
        self.ensure_one()
        specification.ensure_one()
        previous_requirement = previous_requirement or specification.form_id

        # The previous selective mapping omitted fields such as customer_notes,
        # designer_note and design documents.  Odoo's native copy_data handles
        # nested One2many/Many2many commands and preserves future copyable
        # business fields without writing anything to the source record.
        values = specification.copy_data()[0]
        for field_name in (
            'id', 'form_id', 'sale_order_line_ids',
            'job_code_link', 'gdn_number_link',
        ):
            values.pop(field_name, None)

        # The original copy=False attachment links are still useful to the
        # repeated design. Only link the existing files: never transfer or
        # delete their ownership on the original REQ.
        document_fields = (
            'doc_raw_file_ids', 'doc_customer_approved_file_ids',
            'doc_production_layout_ids', 'doc_plate_layout_ids',
            'doc_digital_print_file_ids', 'doc_color_separation_ids',
        )
        for field_name in document_fields:
            values[field_name] = [Command.set(specification[field_name].ids)]

        # Old REQs can contain repeat copies made before the full snapshot
        # logic existed. Restore any missing *technical* values from that
        # design's ancestor while keeping QTY/UOM from the immediate source.
        # Do not fill genuinely empty values on original (non-repeat) designs.
        if specification.is_duplicate_copy and specification.source_specification_id:
            ancestor = specification.source_specification_id
            visited = {specification.id}
            protected = {
                'quantity', 'quantity_uom', 'quantity_uom_id',
                'print_finish_id', 'print_finish_ids', 'standard_feature_ids',
                'sequence', 'no_designs', 'form_id',
                'source_specification_id', 'previous_req_form',
                'is_duplicate_copy', 'design_document_line_ids',
            }
            missing_documents = {
                name for name in document_fields if not specification[name]
            }
            missing_options = {
                name for name in ('print_finish_ids', 'standard_feature_ids')
                if not specification[name]
            }
            while ancestor and ancestor.id not in visited:
                visited.add(ancestor.id)
                ancestor_values = ancestor.copy_data()[0]
                for field_name, value in ancestor_values.items():
                    if field_name in protected or field_name not in self.env[
                        'crm.requirement.specification'
                    ]._fields:
                        continue
                    if values.get(field_name) in (False, None, '', 0, 0.0, []):
                        if value not in (False, None, '', 0, 0.0, []):
                            values[field_name] = value
                for field_name in document_fields:
                    if field_name in missing_documents and ancestor[field_name]:
                        values[field_name] = [Command.set(ancestor[field_name].ids)]
                        missing_documents.discard(field_name)
                for field_name in tuple(missing_options):
                    if ancestor[field_name]:
                        values[field_name] = [Command.set(ancestor[field_name].ids)]
                        missing_options.discard(field_name)
                if not values.get('design_document_line_ids') and ancestor.design_document_line_ids:
                    values['design_document_line_ids'] = ancestor.copy_data()[0].get(
                        'design_document_line_ids', []
                    )
                ancestor = ancestor.source_specification_id

        # Explicitly preserve fields which may have copy=False or computed
        # inverses in previous versions but are part of the editable form.
        for field_name in ('customer_notes', 'designer_note'):
            if not values.get(field_name) and specification[field_name]:
                values[field_name] = specification[field_name]
        values['quantity_uom_id'] = specification.quantity_uom_id.id or False
        # print_finish_id is computed+inverse from the M2M; do not explicitly
        # assign it or Odoo may reduce a multi-selection to just one option.
        values.pop('print_finish_id', None)
        if specification.print_finish_ids:
            values['print_finish_ids'] = [Command.set(specification.print_finish_ids.ids)]
        elif not values.get('print_finish_ids'):
            values['print_finish_ids'] = [Command.set([])]
        if specification.standard_feature_ids:
            values['standard_feature_ids'] = [Command.set(specification.standard_feature_ids.ids)]
        elif not values.get('standard_feature_ids'):
            values['standard_feature_ids'] = [Command.set([])]
        values.update({
            'sequence': sequence,
            'no_designs': sequence,
            'is_duplicate_copy': True,
            'source_specification_id': specification.id,
            'previous_req_form': previous_requirement.name or False,
        })

        # Preserve legacy layer material names and manually saved thicknesses;
        # only look up a product when the source has no product relationship.
        highest_layer = max(int(specification.layer_visible_count or 1), 1)
        for layer_no in range(1, 11):
            tmpl_key = f'layer_{layer_no}_product_tmpl_id'
            variant_key = f'layer_{layer_no}_variant_id'
            material_key = f'layer_{layer_no}_material'
            thickness_key = f'layer_{layer_no}_thickness'
            material_name = values.get(material_key) or specification[material_key]
            template_id = values.get(tmpl_key)
            variant_id = values.get(variant_key)
            if not template_id and material_name:
                product_tmpl = self.env['product.template'].search(
                    [('name', '=', material_name)], limit=1,
                )
                if not product_tmpl:
                    product_tmpl = self.env['product.template'].search(
                        [('name', 'ilike', material_name)], limit=1,
                    )
                template_id = product_tmpl.id or False
            if template_id and variant_id:
                variant = self.env['product.product'].browse(variant_id)
                if variant.product_tmpl_id.id != template_id:
                    variant_id = False
            values[tmpl_key] = template_id or False
            values[variant_key] = variant_id or False
            values[material_key] = material_name or False
            if thickness_key not in values:
                values[thickness_key] = specification[thickness_key] or 0.0
            if template_id or material_name:
                highest_layer = max(highest_layer, layer_no)
        values['layer_visible_count'] = highest_layer
        return values

    def _repeat_specification_commands(
        self, previous_requirement, start_sequence=1,
        excluded_source_ids=None,
    ):
        """Append independent copies; never clear or modify existing designs."""
        self.ensure_one()
        excluded_source_ids = set(excluded_source_ids or ())
        commands = []
        sequence = start_sequence
        for specification in previous_requirement.specification_ids.sorted(
            key=lambda line: (line.sequence, line.id)
        ):
            if specification.id in excluded_source_ids:
                continue
            commands.append(Command.create(
                self._prepare_repeat_specification_values(
                    specification, sequence,
                    previous_requirement=previous_requirement,
                )
            ))
            excluded_source_ids.add(specification.id)
            sequence += 1
        return commands

    def _check_previous_source_selection(self, sources):
        """Validate sources without mutating original Requirement Forms."""
        self.ensure_one()
        if self._origin.id and self._origin in sources:
            raise ValidationError(
                _('A Requirement Form cannot repeat itself.')
            )
        if sources and (
            not self.partner_id or any(
                source.partner_id != self.partner_id for source in sources
            )
        ):
            raise ValidationError(
                _('Previous Req Forms must belong to the selected Customer.')
            )
        invalid = sources.filtered(lambda source: not source.specification_ids)
        if invalid:
            raise ValidationError(_(
                'These previous Requirement Forms have no Product Specifications: %s'
            ) % ', '.join(invalid.mapped('name')))

    @api.constrains('previous_requirement_ids', 'partner_id')
    def _check_previous_requirement_ids(self):
        for rec in self:
            rec._check_previous_source_selection(rec.previous_requirement_ids)

    def _unselected_previous_specification_rows(self, selected_sources):
        """Copied rows whose source REQ is no longer selected.

        Use the CURRENT tag selection, not only the hidden 'loaded' snapshot:
        when an upgraded or unsaved form loses that snapshot, computing the
        difference from it fails to remove the visible copied rows. Manual
        specifications (without a source and copy marker) are not touched.
        """
        self.ensure_one()
        selected_names = set(selected_sources.mapped('name'))
        return self.specification_ids.filtered(
            lambda line: (
                (line.source_specification_id
                 and line.source_specification_id.form_id not in selected_sources)
                or (
                    line.is_duplicate_copy
                    and not line.source_specification_id
                    and line.previous_req_form
                    and line.previous_req_form not in selected_names
                )
            )
        )

    def _duplicate_repeat_specification_rows(self):
        """Only redundant copies of the *same exact source design*.

        A Repeat Job can legitimately contain identical-looking designs from
        different REQs. Never merge those and never delete a row referenced by
        a Sale Order: its production history belongs to that order.
        """
        self.ensure_one()
        grouped = {}
        for line in self.specification_ids.sorted(
            key=lambda row: (row.sequence or 0, row.no_designs or 0)
        ):
            source = line.source_specification_id
            # A few older browser saves dropped the hidden copy flag while
            # retaining the source link. The source link is authoritative.
            if source:
                grouped.setdefault(source.id, []).append(line)

        redundant = self.env['crm.requirement.specification']
        for rows in grouped.values():
            # Preserve a SO-linked row in preference to a temporary copy.
            keeper = next(
                (row for row in rows if row.sale_order_line_ids), rows[0]
            )
            for row in rows:
                if row != keeper and not row.sale_order_line_ids:
                    redundant |= row
        return redundant

    def _remove_persisted_duplicate_repeat_rows(self):
        """Idempotent cleanup after an O2M save; leave source REQs untouched."""
        for rec in self:
            duplicates = rec._duplicate_repeat_specification_rows()
            if duplicates:
                duplicates.with_context(
                    skip_requirement_audit=True,
                    skip_requirement_resequence=True,
                ).unlink()
                self.env['crm.requirement.specification']._resequence_form_lines(rec)

    def _append_unloaded_previous_requirements(self, sources):
        """Server fallback for imports and clients without onchange commands."""
        self.ensure_one()
        self._check_previous_source_selection(sources)
        existing_source_ids = set(
            self.specification_ids.mapped('source_specification_id').ids
        )
        next_sequence = max(
            self.specification_ids.mapped('sequence') or [0]
        ) + 1
        commands = []
        for source in sources.sorted(key=lambda rec: rec.id):
            for specification in source.specification_ids.sorted(
                key=lambda rec: (rec.sequence, rec.id)
            ):
                if specification.id in existing_source_ids:
                    continue
                commands.append(Command.create(
                    self._prepare_repeat_specification_values(
                        specification, next_sequence,
                        previous_requirement=source,
                    )
                ))
                existing_source_ids.add(specification.id)
                next_sequence += 1
        if commands:
            self.with_context(skip_requirement_audit=True).write({
                'specification_ids': commands,
            })
        self.with_context(skip_requirement_audit=True).write({
            'loaded_previous_requirement_ids': [Command.set(
                self.previous_requirement_ids.ids
            )],
        })

    @api.onchange('previous_requirement_ids')
    def _onchange_previous_requirement_ids(self):
        """Import only newly selected REQs; never replace previously added rows."""
        for rec in self:
            selected = rec.previous_requirement_ids
            loaded = rec.loaded_previous_requirement_ids
            # An unchanged hidden snapshot may be absent in an onchange RPC
            # (notably on upgraded, already-saved forms). Use the persisted
            # selection instead of treating every selected REQ as newly added.
            if not loaded and rec._origin.id:
                loaded = (
                    rec._origin.loaded_previous_requirement_ids
                    or rec._origin.previous_requirement_ids
                )
            # A pre-save wizard can sometimes lose its hidden M2M snapshot.
            # A source with visible copied designs has already been imported;
            # never reload its deleted designs while adding a different REQ.
            visible_sources = rec.specification_ids.mapped(
                'source_specification_id.form_id'
            )
            loaded |= visible_sources & selected
            added = selected - loaded
            try:
                rec._check_previous_source_selection(selected)
            except ValidationError as error:
                rec.previous_requirement_ids = [Command.set(loaded.ids)]
                return {
                    'warning': {
                        'title': _('Invalid Previous Requirement'),
                        'message': str(error),
                    }
                }

            # Selection is authoritative. The hidden loaded M2M may be empty
            # even while copied rows are visible, so delta-only removal is
            # insufficient (the user could remove a tag but keep all rows).
            removed_lines = rec._unselected_previous_specification_rows(selected)
            if removed_lines.filtered(lambda line: line.sale_order_line_ids):
                rec.previous_requirement_ids = [Command.set(loaded.ids)]
                return {
                    'warning': {
                        'title': _('Previous REQ is used by a Sale Order'),
                        'message': _(
                            'Cannot remove a previous REQ whose copied '
                            'designs are already linked to a Sale Order.'
                        ),
                    },
                }
            if removed_lines:
                rec.specification_ids = rec.specification_ids - removed_lines

            # Normalize already imported lines BEFORE adding any new source.
            # Also fixes old duplicated copies during the very next edit.
            duplicates = rec._duplicate_repeat_specification_rows()
            if duplicates:
                rec.specification_ids = rec.specification_ids - duplicates

            next_sequence = max(
                rec.specification_ids.mapped('sequence') or [0]
            ) + 1
            new_commands = []
            existing_source_ids = set(
                rec.specification_ids.mapped('source_specification_id').ids
            )
            for previous in added.sorted(key=lambda source: source.id):
                commands = rec._repeat_specification_commands(
                    previous, start_sequence=next_sequence,
                    excluded_source_ids=existing_source_ids,
                )
                new_commands.extend(commands)
                existing_source_ids.update(previous.specification_ids.ids)
                next_sequence += len(commands)
            if new_commands:
                rec.update({'specification_ids': new_commands})
            # Onchange commands can be replayed by the client after a widget
            # update. Enforce one current row per source specification.
            duplicates = rec._duplicate_repeat_specification_rows()
            if duplicates:
                rec.specification_ids = rec.specification_ids - duplicates
            rec.loaded_previous_requirement_ids = [Command.set(selected.ids)]
            if selected:
                rec.repeat_job = True
                rec.new_job = False

    @api.onchange('previous_requirement_id')
    def _onchange_previous_requirement_id(self):
        """Legacy single-source API remains supported without clearing rows."""
        for rec in self:
            previous = rec.previous_requirement_id
            if previous and previous not in rec.previous_requirement_ids:
                rec.previous_requirement_ids = [Command.link(previous.id)]
                rec._onchange_previous_requirement_ids()

    @api.depends('specification_ids')
    def _compute_next_design_number(self):
        for rec in self:
            rec.next_design_number = len(rec.specification_ids) + 1

    @api.onchange('specification_ids')
    def _onchange_specification_ids_numbering(self):
        for rec in self:
            # Odoo's editable x2many widget can replay an import's create
            # commands after the source-selector onchange has completed.
            # Normalize the current rows here as well, before numbering them.
            # The helper groups by exact source specification ID and protects
            # rows already referenced by Sale Orders. No source is reloaded.
            if rec.repeat_job:
                redundant = rec._duplicate_repeat_specification_rows()
                if redundant:
                    rec.specification_ids = rec.specification_ids - redundant

            # A manually deleted design must stay deleted: this onchange
            # *only* normalizes/renumbers the rows still in this form.
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
        # Repeat jobs keep the exact existing Job Code from the previous
        # design; a fresh serial is reserved for New Jobs only.
        if self.repeat_job and source:
            source_line = specification._get_repeat_job_source_line(
                gdn_configuration=values.get('gdn_configuration_id')
            )
            if source_line:
                values['job_code'] = source_line.job_code
        for layer_no in range(1, 11):
            template = specification[f'layer_{layer_no}_product_tmpl_id']
            variant = specification[f'layer_{layer_no}_variant_id']
            values[f'req_layer_{layer_no}_product_tmpl_id'] = template.id or False
            values[f'req_layer_{layer_no}_variant_id'] = variant.id or False
        return values

    def _sync_specifications_to_sale_order(self, order):
        self.ensure_one()
        order.ensure_one()
        if order.requirement_form_id != self:
            raise ValidationError(_(
                'Cannot synchronize another Requirement Form\'s Sale Order.'
            ))
        # Confirmed/cancelled orders are historical records; never rewrite them
        # when a later Repeat Requirement is edited or submitted.
        if order.state not in ('draft', 'sent'):
            return
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
                lambda order: order.state in ('draft', 'sent')
                and order.payment_term_id != self.payment_term_id
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

        # Refresh only this form's draft quotations. A confirmed Sale Order
        # and its production snapshots must never be rewritten by later REQs.
        for linked_order in orders.filtered(
            lambda order: order.state in ('draft', 'sent')
        ):
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
            'loaded_previous_requirement_ids',
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
        if previous_id and 'previous_requirement_ids' not in vals:
            # Legacy one-source callers can keep using the original field.
            vals['previous_requirement_ids'] = [Command.link(previous_id)]
        prior_sources = {rec.id: rec.previous_requirement_ids for rec in self}
        # Source rows connected to existing SOs must never be silently
        # deleted, even if the client includes O2M delete commands.
        linked_source_lines = {
            rec.id: rec.specification_ids.filtered(
                lambda line: line.source_specification_id
                and line.sale_order_line_ids
            )
            for rec in self
        }
        sources_changed = 'previous_requirement_ids' in vals
        specs_supplied = 'specification_ids' in vals

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
        if sources_changed or specs_supplied:
            for rec in self:
                selected = rec.previous_requirement_ids
                previously = prior_sources.get(rec.id, selected)
                removed = previously - selected if sources_changed else self.env[
                    'crm.requirement.form'
                ]
                # Never erase an already-confirmed SO's source line; raising
                # here rolls back all commands from super().write().
                protected = linked_source_lines.get(rec.id)
                if protected and any(
                    not line.exists()
                    or line.source_specification_id.form_id in removed
                    for line in protected
                ):
                    raise ValidationError(_(
                        'Cannot delete a Repeat Job specification already '
                        'used by a Sale Order.'
                    ))
                if sources_changed:
                    # Also handle old/corrupted loaded-source snapshots. The
                    # chosen REQs, not the prior snapshot, decide which copied
                    # designs belong here; protect all SO-linked rows.
                    remove_rows = rec._unselected_previous_specification_rows(
                        selected
                    )
                    if remove_rows.filtered(lambda line: line.sale_order_line_ids):
                        raise ValidationError(_(
                            'Cannot remove a Repeat Job specification already '
                            'used by a Sale Order.'
                        ))
                    if remove_rows:
                        remove_rows.with_context(
                            skip_requirement_audit=True,
                            skip_requirement_resequence=True,
                        ).unlink()
                if sources_changed and not specs_supplied:
                    # An API/legacy client with no O2M commands still gets
                    # only the newly chosen source, once. A saved manual line
                    # deletion never causes a source to be imported again.
                    added = selected - previously
                    if added:
                        rec._append_unloaded_previous_requirements(added)
                if rec.repeat_job:
                    rec._remove_persisted_duplicate_repeat_rows()
                if sources_changed and rec.loaded_previous_requirement_ids != selected:
                    rec.with_context(skip_requirement_audit=True).write({
                        'loaded_previous_requirement_ids': [Command.set(selected.ids)],
                    })
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
            if previous_id and 'previous_requirement_ids' not in vals:
                vals['previous_requirement_ids'] = [Command.link(previous_id)]
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
        for record, values in zip(records, vals_list):
            if record.previous_requirement_ids:
                if 'specification_ids' not in values:
                    record._append_unloaded_previous_requirements(
                        record.previous_requirement_ids
                    )
                else:
                    record.with_context(skip_requirement_audit=True).write({
                        'loaded_previous_requirement_ids': [Command.set(
                            record.previous_requirement_ids.ids
                        )],
                    })
            if record.repeat_job:
                record._remove_persisted_duplicate_repeat_rows()
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
                rec.previous_requirement_ids
                or rec.previous_requirement_id
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
