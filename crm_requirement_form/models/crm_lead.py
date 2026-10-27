from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    business_licence = fields.Char(
        string='Business Licence',
        tracking=True,
    )
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        tracking=True,
        help='WhatsApp number synchronized with the linked Contact.',
    )
    industry_category_id = fields.Many2one(
        'res.partner.industry',
        string='Industry Category',
        index=True,
        tracking=True,
        help='Industry category synchronized with the linked customer contact.',
    )
    industry_category_locked = fields.Boolean(
        string='Industry Category Locked',
        compute='_compute_industry_category_locked',
        help='Industry Category is locked only when the selected contact already has an Industry.',
    )
    customer_short_name = fields.Char(
        string='Customer Short Name',
        tracking=True,
        help='Short customer code used in requirement IDs, for example TLS.',
    )
    vat_no = fields.Char(
        string='VAT No.',
        tracking=True,
        help='VAT number synchronized with the linked Contact (Tax ID) and the Requirement Forms.',
    )
    generated_customer_id = fields.Char(
        string='System Generated Customer ID',
        copy=False,
        readonly=True,
        tracking=True,
        help='Saudi customers use 01-00001 format; non-Saudi customers use 02-00001 format.',
    )
    requirement_form_count = fields.Integer(
        string='Requirement Forms',
        compute='_compute_requirement_form_count',
    )
    customer_rating_count = fields.Integer(
        string='Customer Ranking',
        compute='_compute_customer_rating_count',
    )
    customer_rating_rank = fields.Selection(
        selection=[('a', 'A'), ('b', 'B'), ('c', 'C')],
        string='Customer AVG Rank',
        compute='_compute_customer_rating_rank',
    )
    requirement_summary_html = fields.Html(
        string='Requirement Summary',
        readonly=True,
        sanitize=False,
        help=(
            'Automatic summary of every Product Specification from all '
            'Requirement Forms linked to this opportunity.'
        ),
    )

    def _refresh_requirement_summary(self):
        """Build compact two-column cards from populated REQ specification data."""
        from html import escape

        RequirementForm = self.env['crm.requirement.form']

        def text(value):
            return escape(str(value)) if value not in (False, None, '') else ''

        def row(label, value):
            value = text(value)
            if not value:
                return ''
            return (
                '<div class="o_crm_req_summary_row" style="display:flex;gap:12px;padding:7px 0;'
                'border-bottom:1px solid #edf0f2;align-items:flex-start;width:100%;">'
                '<div style="font-size:12px;font-weight:700;color:#5b6470;flex:0 0 145px;'
                'width:145px;white-space:nowrap;">'
                f'{escape(label)}</div>'
                '<div style="font-size:13px;line-height:1.45;color:#17212b;flex:1 1 auto;'
                'min-width:0;white-space:normal;overflow-wrap:break-word;word-break:normal;">'
                f'{value}</div></div>'
            )

        def section(title, rows):
            content = ''.join(item for item in rows if item)
            if not content:
                return ''
            return (
                '<div style="padding:10px 14px 4px;">'
                '<div style="font-size:11px;font-weight:800;letter-spacing:.04em;'
                'text-transform:uppercase;color:#714b67;margin-bottom:2px;">'
                f'{escape(title)}</div>{content}</div>'
            )

        for lead in self:
            forms = RequirementForm.search(
                [('lead_id', '=', lead.id), ('feasibility_yes', '=', True)],
                order='id asc',
            )
            cards = []
            card_index = 0
            for form in forms:
                specifications = form.specification_ids.sorted(
                    key=lambda rec: (rec.sequence, rec.id)
                )
                for spec in specifications:
                    card_index += 1
                    design_name = spec.design_name or f'Design {card_index}'
                    quantity_uom = (
                        spec.quantity_uom_id.name
                        or dict(spec._fields['quantity_uom'].selection).get(
                            spec.quantity_uom, ''
                        )
                    )
                    print_finish = ', '.join(spec.print_finish_ids.mapped('name'))
                    if not print_finish:
                        print_finish = (
                            spec.print_finish_id.display_name
                            if spec.print_finish_id else spec.print_finish or ''
                        )
                    color_reference = dict(
                        spec._fields['color_reference'].selection
                    ).get(spec.color_reference, spec.color_reference or '')
                    color_reference_type = dict(
                        spec._fields['color_reference_type'].selection
                    ).get(
                        spec.color_reference_type,
                        spec.color_reference_type or '',
                    )

                    # Keep the CRM Requirement Summary intentionally concise.
                    # Only the business fields requested from each product line are shown.
                    valve_label = ''
                    if spec.valve:
                        valve_label = dict(
                            spec._fields['valve_type'].selection
                        ).get(spec.valve_type, spec.valve_type or 'Yes')

                    summary_rows = [
                        row('Type', spec.summary_type),
                        row('Dimensions', spec.summary_dimensions),
                        row('Weight', f'{spec.weight:g} g' if spec.weight else ''),
                        row('Material - Structure', spec.summary_material_structure),
                        row('Print and Finish', print_finish),
                        row('Features', spec.features),
                        row('Valve', valve_label),
                        row('Quantity', (
                            f'{spec.quantity:g} {quantity_uom}'.strip()
                            if spec.quantity else ''
                        )),
                    ]

                    body = section('Product Specification', summary_rows)

                    cards.append(
                        '<div class="o_crm_req_summary_card" style="border:1px solid #d8dde3;border-radius:12px;'
                        'background:#fff;overflow:hidden;min-width:0;align-self:start;'
                        'box-shadow:0 1px 4px rgba(0,0,0,.07);">'
                        '<div style="padding:12px 14px;background:#f7f3f6;'
                        'border-bottom:1px solid #e2d9df;">'
                        '<div style="font-size:15px;font-weight:800;color:#714b67;">'
                        f'{escape(design_name)}</div>'
                        '<div style="font-size:11px;color:#747b84;margin-top:3px;">'
                        f'{escape(form.name or "Requirement Form")}</div></div>'
                        f'{body}<div style="height:8px;"></div></div>'
                    )
            lead.requirement_summary_html = (
                '<div class="o_crm_req_summary_grid" style="display:grid;'
                'grid-template-columns:repeat(2,minmax(360px,1fr));gap:16px;'
                'align-items:start;width:100%;max-width:1100px;">'
                + ''.join(cards)
                + '</div>'
            ) if cards else False

    @api.depends('partner_id', 'partner_id.industry_id', 'partner_id.parent_id.industry_id')
    def _compute_industry_category_locked(self):
        for lead in self:
            commercial_partner = lead.partner_id.commercial_partner_id
            lead.industry_category_locked = bool(
                commercial_partner and commercial_partner.industry_id
            )

    @api.depends(
        'email_domain_criterion',
        'email_normalized',
        'partner_id',
        'phone_sanitized',
        'partner_name',
    )
    def _compute_potential_lead_duplicates(self):
        """Extend Odoo duplicate detection with exact Company Name matches.

        The standard CRM duplicate logic is preserved (email domain, phone, and
        commercial partner). Leads sharing the same non-empty Company Name are
        additionally exposed through the standard Similar Leads smart button.
        """
        super()._compute_potential_lead_duplicates()
        Lead = self.with_context(active_test=False)
        for lead in self:
            company_name = (lead.partner_name or '').strip()
            if not company_name:
                continue

            company_duplicates = Lead.search([
                ('id', '!=', lead._origin.id),
                ('partner_name', '=ilike', company_name),
            ])
            duplicate_leads = lead.duplicate_lead_ids | company_duplicates | lead
            lead.duplicate_lead_ids = duplicate_leads
            lead.duplicate_lead_count = len(duplicate_leads - lead)

    @api.model
    def _prepare_automatic_opportunity_name(self, vals, record=False):
        """Build Salesperson Name_COMPANY NAME for the CRM opportunity title."""
        user = self.env['res.users'].browse(vals.get('user_id')).exists() if vals.get('user_id') else False
        if not user and record:
            user = record.user_id
        if not user:
            user = self.env.user

        company_name = (vals.get('partner_name') or '').strip()
        partner_id = vals.get('partner_id')
        if not company_name and partner_id:
            partner = self.env['res.partner'].browse(partner_id).exists()
            company_name = (partner.commercial_partner_id.name or partner.name or '').strip()
        if not company_name and record:
            company_name = (
                record.partner_name
                or record.partner_id.commercial_partner_id.name
                or record.partner_id.name
                or ''
            ).strip()

        salesperson_name = (user.name or '').strip() if user else ''
        if salesperson_name and company_name:
            return f'{salesperson_name}_{company_name}'
        return False

    @api.onchange('user_id', 'partner_id', 'partner_name')
    def _onchange_automatic_opportunity_name(self):
        for lead in self:
            automatic_name = lead._prepare_automatic_opportunity_name({}, record=lead)
            if automatic_name:
                lead.name = automatic_name

    @api.constrains('customer_short_name', 'partner_id')
    def _check_customer_short_name_unique(self):
        for lead in self:
            short_name = (lead.customer_short_name or '').strip()
            if not short_name:
                continue

            other_lead_domain = [
                ('id', '!=', lead.id),
                ('customer_short_name', '=ilike', short_name),
            ]
            if lead.partner_id:
                commercial_partner = lead.partner_id.commercial_partner_id
                same_customer_leads = self.sudo().search(other_lead_domain)
                same_customer_leads = same_customer_leads.filtered(
                    lambda item: item.partner_id
                    and item.partner_id.commercial_partner_id == commercial_partner
                )
                if self.sudo().search_count(other_lead_domain) > len(same_customer_leads):
                    raise ValidationError(
                        _('Customer Short Name must be unique. "%s" is already used by another customer.')
                        % short_name
                    )
            elif self.sudo().search_count(other_lead_domain):
                raise ValidationError(
                    _('Customer Short Name must be unique. "%s" is already used by another customer.')
                    % short_name
                )

            partner_domain = [
                ('parent_id', '=', False),
                ('ref', '=ilike', short_name),
            ]
            if lead.partner_id:
                partner_domain.append(('id', '!=', lead.partner_id.commercial_partner_id.id))
            if self.env['res.partner'].sudo().search_count(partner_domain):
                raise ValidationError(
                    _('Customer Short Name must be unique. "%s" is already used by another customer.')
                    % short_name
                )

    @api.onchange('customer_short_name', 'partner_id')
    def _onchange_customer_short_name_unique_warning(self):
        for lead in self:
            short_name = (lead.customer_short_name or '').strip()
            if not short_name:
                continue

            lead_domain = [('customer_short_name', '=ilike', short_name)]
            if lead._origin.id:
                lead_domain.append(('id', '!=', lead._origin.id))
            other_leads = self.sudo().search(lead_domain)
            if lead.partner_id:
                commercial_partner = lead.partner_id.commercial_partner_id
                other_leads = other_leads.filtered(
                    lambda item: not item.partner_id
                    or item.partner_id.commercial_partner_id != commercial_partner
                )
            if other_leads:
                return {
                    'warning': {
                        'title': _('Customer Short Name Must Be Unique'),
                        'message': _('The Customer Short Name "%s" is already used by another customer. Please enter a unique short name.') % short_name,
                    }
                }

            partner_domain = [
                ('parent_id', '=', False),
                ('ref', '=ilike', short_name),
            ]
            if lead.partner_id:
                partner_domain.append(('id', '!=', lead.partner_id.commercial_partner_id.id))
            if self.env['res.partner'].sudo().search_count(partner_domain):
                return {
                    'warning': {
                        'title': _('Customer Short Name Must Be Unique'),
                        'message': _('The Customer Short Name "%s" is already used by another customer. Please enter a unique short name.') % short_name,
                    }
                }
        return {}

    def _ensure_customer_code_for_opportunity(self):
        """Generate/synchronize Customer Code only for opportunities.

        A CRM lead must not consume a Customer Code while it is still a lead.
        The code is assigned when the record becomes an opportunity. If the
        opportunity is linked to an existing customer that already has a code,
        that customer code is reused so CRM and Contacts stay synchronized.
        """
        for lead in self.filtered(lambda item: item.type == 'opportunity'):
            commercial_partner = lead.partner_id.commercial_partner_id
            country = lead.country_id or commercial_partner.country_id
            expected_prefix = lead._get_customer_id_prefix(country)

            partner_code = (commercial_partner.customer_code or '').strip()
            lead_code = (lead.generated_customer_id or '').strip()

            if partner_code:
                customer_code = partner_code
            elif lead_code and lead_code.startswith(f'{expected_prefix}-'):
                customer_code = lead_code
            else:
                customer_code = lead._generate_customer_id(
                    country=country,
                    prefix=expected_prefix,
                )

            if commercial_partner and commercial_partner.customer_code != customer_code:
                commercial_partner.with_context(
                    skip_supplier_customer_code_cleanup=True,
                    skip_customer_code_country_sync=True,
                ).write({'customer_code': customer_code})

            if lead.generated_customer_id != customer_code:
                super(CrmLead, lead.with_context(
                    skip_customer_code_partner_sync=True,
                )).write({'generated_customer_id': customer_code})

        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            automatic_name = self._prepare_automatic_opportunity_name(vals)
            if automatic_name:
                vals['name'] = automatic_name

        # If an existing Contact already has an Industry, that value is the
        # source of truth. If the Contact Industry is empty, keep the Industry
        # selected on the CRM form so it can be written back to the Contact.
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if not partner_id:
                continue
            partner = self.env['res.partner'].browse(partner_id).exists()
            commercial_partner = partner.commercial_partner_id if partner else False
            if commercial_partner and commercial_partner.industry_id:
                vals['industry_category_id'] = commercial_partner.industry_id.id

            # When an existing customer is selected (including through the CRM
            # Convert to Opportunity wizard), the customer master is the source
            # of truth for the short name.  Populate it on the CRM record before
            # create so Other_Info immediately shows the same value.
            if commercial_partner:
                # Customer master wins when it has a short name. If the
                # customer has none yet (e.g. new customer created by the
                # Convert to Opportunity wizard), keep the name typed on the
                # lead; it is pushed to the customer right after create.
                if commercial_partner.ref:
                    vals['customer_short_name'] = commercial_partner.ref
                # Same rule for VAT No.: the customer master wins when it has one.
                if commercial_partner.vat:
                    vals['vat_no'] = commercial_partner.vat

        leads = super().create(vals_list)
        leads._ensure_customer_code_for_opportunity()
        leads._sync_industry_category_on_create()
        leads._sync_customer_data_to_partner()
        leads.filtered('partner_id')._sync_vat_with_partner()
        leads._sync_short_name_with_partner()
        for lead, source_vals in zip(leads, vals_list):
            partner = lead.partner_id
            if not partner:
                continue
            if source_vals.get('whatsapp_number'):
                if partner.whatsapp_number != lead.whatsapp_number:
                    partner.with_context(
                        skip_whatsapp_related_sync=True,
                    ).write({'whatsapp_number': lead.whatsapp_number})
            elif partner.whatsapp_number and (
                lead.whatsapp_number != partner.whatsapp_number
            ):
                super(CrmLead, lead.with_context(
                    skip_whatsapp_partner_sync=True,
                )).write({'whatsapp_number': partner.whatsapp_number})
        return leads

    def write(self, vals):
        if self.env.context.get('skip_customer_code_partner_sync'):
            return super().write(vals)

        vals = dict(vals)

        # Existing Contact with an Industry => Contact Industry is authoritative.
        # Existing Contact without an Industry => CRM Industry remains editable and
        # a value selected here will be synchronized back to the Contact.
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id']).exists()
            commercial_partner = partner.commercial_partner_id if partner else False
            if commercial_partner and commercial_partner.industry_id:
                vals['industry_category_id'] = commercial_partner.industry_id.id
            elif (
                'industry_category_id' not in vals
                and len(self) == 1
                and self.type == 'lead'
                and not self.partner_id
                and self.industry_category_id
            ):
                # During Lead -> Opportunity conversion Odoo first assigns a
                # customer. If the new customer has no Industry, preserve the
                # selected Lead Industry and sync it to that customer below.
                vals['industry_category_id'] = self.industry_category_id.id
            elif 'industry_category_id' not in vals:
                # A switch from a previously selected Contact with no matching
                # Industry must not retain that old Contact's Industry.
                vals['industry_category_id'] = False

            # Linking/changing to an existing customer must fetch its Customer
            # Short Name into CRM.  Do not wait for a later save or requirement
            # form action.
            if commercial_partner:
                # Short name follows the selected customer. If the new
                # customer has no short name, keep the one typed on this lead
                # (it is pushed to the customer below); a short name inherited
                # from a previous customer is cleared.
                if commercial_partner.ref:
                    vals['customer_short_name'] = commercial_partner.ref
                elif 'customer_short_name' not in vals and any(
                    lead.partner_id
                    and lead.partner_id.commercial_partner_id != commercial_partner
                    for lead in self
                ):
                    vals['customer_short_name'] = False
                # VAT No. follows the selected customer. If the new customer has
                # no VAT yet, a VAT typed on this lead is kept (it is pushed to
                # the customer below); a VAT inherited from a previous customer
                # is cleared.
                if commercial_partner.vat:
                    vals['vat_no'] = commercial_partner.vat
                elif 'vat_no' not in vals and any(
                    lead.partner_id
                    and lead.partner_id.commercial_partner_id != commercial_partner
                    for lead in self
                ):
                    vals['vat_no'] = False
        elif (
            'industry_category_id' in vals
            and 'partner_id' not in vals
            and len(self) == 1
            and self.partner_id
            and self.partner_id.commercial_partner_id.industry_id
        ):
            vals['industry_category_id'] = (
                self.partner_id.commercial_partner_id.industry_id.id
            )
        if {'user_id', 'partner_id', 'partner_name'} & set(vals):
            # A multi-record write can have a different current company name per lead.
            if len(self) == 1:
                automatic_name = self._prepare_automatic_opportunity_name(vals, record=self)
                if automatic_name:
                    vals['name'] = automatic_name

        result = super().write(vals)
        if len(self) > 1 and {'user_id', 'partner_id', 'partner_name'} & set(vals):
            for lead in self:
                automatic_name = lead._prepare_automatic_opportunity_name({}, record=lead)
                if automatic_name and lead.name != automatic_name:
                    super(CrmLead, lead).write({'name': automatic_name})
        if {'type', 'country_id', 'partner_id'} & set(vals):
            self._ensure_customer_code_for_opportunity()

        if {'country_id', 'partner_id'} & set(vals):
            for lead in self.filtered(lambda item: item.type == 'opportunity'):
                country = lead.country_id or lead.partner_id.country_id
                expected_prefix = lead._get_customer_id_prefix(country)
                current_code = lead.generated_customer_id or ''
                has_requirement = bool(
                    self.env['crm.requirement.form'].search_count([
                        ('lead_id', '=', lead.id),
                    ])
                )
                must_generate = (
                    not current_code
                    or current_code.startswith('CUS_')
                    or (
                        not has_requirement
                        and current_code[:2] in ('01', '02')
                        and current_code[:2] != expected_prefix
                    )
                )
                if must_generate:
                    lead.with_context(skip_customer_code_partner_sync=True).write({
                        'generated_customer_id': lead._generate_customer_id(
                            prefix=expected_prefix
                        ),
                    })

        if {
            'country_id',
            'partner_id',
            'generated_customer_id',
            'customer_short_name',
        } & set(vals):
            self._sync_customer_data_to_partner()

        if (
            {'customer_short_name', 'partner_id'} & set(vals)
            and not self.env.context.get('skip_short_name_partner_sync')
        ):
            self._sync_short_name_with_partner(
                prefer_lead=(
                    'customer_short_name' in vals and 'partner_id' not in vals
                ),
            )

        if (
            {'vat_no', 'partner_id'} & set(vals)
            and not self.env.context.get('skip_vat_partner_sync')
        ):
            self._sync_vat_with_partner(
                prefer_lead='vat_no' in vals and 'partner_id' not in vals,
            )

        if (
            {'industry_category_id', 'partner_id'} & set(vals)
            and not self.env.context.get('skip_industry_partner_sync')
        ):
            self._sync_industry_category_after_write(
                industry_changed='industry_category_id' in vals,
            )

        if 'user_id' in vals:
            for lead in self:
                requirement_forms = self.env['crm.requirement.form'].search([
                    ('lead_id', '=', lead.id),
                ])
                if requirement_forms:
                    requirement_forms.write({
                        'user_id': (lead.user_id or self.env.user).id,
                    })

        if {'campaign_id', 'medium_id', 'source_id'} & set(vals):
            # Open quotations follow the Opportunity's Campaign/Medium/Source.
            open_orders = self.env['sale.order'].search([
                ('opportunity_id', 'in', self.ids),
                ('state', 'in', ('draft', 'sent')),
            ])
            for order in open_orders:
                lead = order.opportunity_id
                order_vals = {
                    name: lead[name].id or False
                    for name in ('campaign_id', 'medium_id', 'source_id')
                    if name in vals and order[name] != lead[name]
                }
                if order_vals:
                    order.write(order_vals)

        if {'whatsapp_number', 'partner_id'} & set(vals):
            for lead in self:
                partner = lead.partner_id
                if (
                    partner
                    and not self.env.context.get('skip_whatsapp_partner_sync')
                ):
                    if 'whatsapp_number' in vals:
                        if partner.whatsapp_number != lead.whatsapp_number:
                            partner.with_context(
                                skip_whatsapp_related_sync=True,
                            ).write({
                                'whatsapp_number': lead.whatsapp_number or False,
                            })
                    elif partner.whatsapp_number:
                        if lead.whatsapp_number != partner.whatsapp_number:
                            super(CrmLead, lead.with_context(
                                skip_whatsapp_partner_sync=True,
                            )).write({
                                'whatsapp_number': partner.whatsapp_number,
                            })
                    elif lead.whatsapp_number:
                        partner.with_context(
                            skip_whatsapp_related_sync=True,
                        ).write({'whatsapp_number': lead.whatsapp_number})

                requirement_forms = self.env['crm.requirement.form'].search([
                    ('lead_id', '=', lead.id),
                ])
                if requirement_forms:
                    effective_number = (
                        partner.whatsapp_number
                        if partner and partner.whatsapp_number
                        else lead.whatsapp_number
                    )
                    requirement_forms.with_context(
                        skip_whatsapp_partner_sync=True,
                    ).write({
                        'whatsapp_number': effective_number or False,
                    })
        return result

    def _sync_industry_category_on_create(self):
        """Synchronize Industry for a newly created CRM lead.

        A Contact that already has an Industry remains authoritative. When the
        Contact Industry is empty, a CRM-selected Industry is copied to the
        Contact instead of being cleared from the CRM lead.
        """
        for lead in self:
            commercial_partner = lead.partner_id.commercial_partner_id
            if not commercial_partner:
                continue

            if commercial_partner.industry_id:
                if lead.industry_category_id != commercial_partner.industry_id:
                    super(CrmLead, lead.with_context(
                        skip_industry_partner_sync=True,
                    )).write({
                        'industry_category_id': commercial_partner.industry_id.id,
                    })
                continue

            if lead.industry_category_id:
                commercial_partner.with_context(
                    skip_industry_lead_sync=True,
                ).write({
                    'industry_id': lead.industry_category_id.id,
                })

    def _sync_industry_category_after_write(self, industry_changed=False):
        """Synchronize CRM Industry with the selected Contact.

        - Contact has Industry: keep CRM equal to it.
        - Contact Industry is empty: allow CRM selection and copy it to Contact.
        """
        for lead in self:
            commercial_partner = lead.partner_id.commercial_partner_id
            if not commercial_partner:
                continue

            if commercial_partner.industry_id:
                if lead.industry_category_id != commercial_partner.industry_id:
                    super(CrmLead, lead.with_context(
                        skip_industry_partner_sync=True,
                    )).write({
                        'industry_category_id': commercial_partner.industry_id.id,
                    })
                continue

            if industry_changed and lead.industry_category_id:
                commercial_partner.with_context(
                    skip_industry_lead_sync=True,
                ).write({
                    'industry_id': lead.industry_category_id.id,
                })

    @api.onchange('partner_id')
    def _onchange_partner_industry_category(self):
        for lead in self:
            if lead.partner_id:
                lead.industry_category_id = (
                    lead.partner_id.commercial_partner_id.industry_id
                )
                if lead.partner_id.whatsapp_number:
                    lead.whatsapp_number = lead.partner_id.whatsapp_number
                # Show the existing customer's short name immediately in CRM.
                partner_ref = lead.partner_id.commercial_partner_id.ref
                if partner_ref:
                    lead.customer_short_name = partner_ref
                elif (
                    lead._origin.partner_id
                    and lead._origin.partner_id.commercial_partner_id
                    != lead.partner_id.commercial_partner_id
                ):
                    lead.customer_short_name = False
                lead.vat_no = (
                    lead.partner_id.commercial_partner_id.vat or False
                )
            else:
                # No existing Contact: allow the user to select an Industry for
                # the new customer flow.
                lead.industry_category_id = False

    def init(self):
        """Fill blank CRM VAT No. / Short Name from the linked customer."""
        super().init()
        self.env.cr.execute("""
            UPDATE crm_lead lead
               SET customer_short_name = cp.ref
              FROM res_partner p
              JOIN res_partner cp ON cp.id = COALESCE(p.commercial_partner_id, p.id)
             WHERE lead.partner_id = p.id
               AND COALESCE(cp.ref, '') <> ''
               AND COALESCE(lead.customer_short_name, '') = ''
        """)
        self.env.cr.execute("SELECT to_regclass('crm_requirement_form')")
        if self.env.cr.fetchone()[0]:
            self.env.cr.execute("""
                UPDATE crm_requirement_form form
                   SET customer_short_name = cp.ref
                  FROM res_partner p
                  JOIN res_partner cp ON cp.id = COALESCE(p.commercial_partner_id, p.id)
                 WHERE form.partner_id = p.id
                   AND COALESCE(cp.ref, '') <> ''
                   AND COALESCE(form.customer_short_name, '') = ''
            """)
        self.env.cr.execute("""
            UPDATE crm_lead lead
               SET vat_no = cp.vat
              FROM res_partner p
              JOIN res_partner cp ON cp.id = COALESCE(p.commercial_partner_id, p.id)
             WHERE lead.partner_id = p.id
               AND COALESCE(cp.vat, '') <> ''
               AND COALESCE(lead.vat_no, '') = ''
        """)

    def _sync_short_name_with_partner(self, prefer_lead=False):
        """Keep Customer Short Name identical on CRM, Contact (ref) and Requirement Forms.

        prefer_lead=True  -> edited on the CRM record: push it to the Contact.
        prefer_lead=False -> the Contact is the source of truth when it has a
                             short name; otherwise the CRM value is pushed to it.
        Every Requirement Form of the lead is aligned in both cases.
        """
        RequirementForm = self.env['crm.requirement.form']
        for lead in self:
            partner = lead.partner_id.commercial_partner_id
            lead_name = (lead.customer_short_name or '').strip() or False
            if partner:
                if prefer_lead:
                    if lead_name and partner.ref != lead_name:
                        partner.write({'ref': lead_name})
                elif partner.ref:
                    if lead.customer_short_name != partner.ref:
                        super(CrmLead, lead.with_context(
                            skip_short_name_partner_sync=True,
                        )).write({'customer_short_name': partner.ref})
                elif lead_name:
                    partner.write({'ref': lead_name})
                partner._sync_short_name_to_related_records()

            effective = (
                (partner.ref if partner else False)
                or (lead.customer_short_name or False)
            )
            forms = RequirementForm.search([('lead_id', '=', lead.id)]).filtered(
                lambda form: (form.customer_short_name or False) != effective
            )
            if forms:
                forms.with_context(skip_short_name_partner_sync=True).write({
                    'customer_short_name': effective,
                })

    def _sync_vat_with_partner(self, prefer_lead=False):
        """Keep VAT No. identical on CRM, Contact and Requirement Forms.

        prefer_lead=True  -> the VAT was edited on the CRM record: push it to
                             the Contact.
        prefer_lead=False -> the Contact is the source of truth when it has a
                             VAT; otherwise a VAT typed on the CRM record is
                             pushed to the Contact.
        In both cases every Requirement Form of the lead is aligned.
        """
        RequirementForm = self.env['crm.requirement.form']
        for lead in self:
            partner = lead.partner_id.commercial_partner_id
            if partner:
                if prefer_lead:
                    if (partner.vat or False) != (lead.vat_no or False):
                        partner.with_context(skip_vat_related_sync=True).write({
                            'vat': lead.vat_no or False,
                        })
                elif partner.vat:
                    if lead.vat_no != partner.vat:
                        super(CrmLead, lead.with_context(
                            skip_vat_partner_sync=True,
                        )).write({'vat_no': partner.vat})
                elif lead.vat_no:
                    partner.with_context(skip_vat_related_sync=True).write({
                        'vat': lead.vat_no,
                    })
                # Other CRM records / forms of the same customer follow too.
                partner._sync_vat_to_related_records()

            effective_vat = (partner.vat if partner else False) or lead.vat_no or False
            forms = RequirementForm.search([('lead_id', '=', lead.id)]).filtered(
                lambda form: (form.vat_no or False) != effective_vat
            )
            if forms:
                forms.with_context(skip_vat_partner_sync=True).write({
                    'vat_no': effective_vat,
                })

    def _sync_customer_data_to_partner(self):
        for lead in self:
            partner = lead.partner_id
            if not partner:
                continue

            values = {}
            if lead.country_id and partner.country_id != lead.country_id:
                values['country_id'] = lead.country_id.id
            commercial_partner = partner.commercial_partner_id
            if (
                lead.type == 'opportunity'
                and lead.generated_customer_id
                and commercial_partner.customer_code != lead.generated_customer_id
            ):
                values['customer_code'] = lead.generated_customer_id
            if lead.customer_short_name and partner.ref != lead.customer_short_name:
                values['ref'] = lead.customer_short_name
            if values:
                partner.write(values)

    @api.onchange('country_id', 'partner_id')
    def _onchange_customer_country_generate_code(self):
        for lead in self:
            if lead.type != 'opportunity':
                continue
            country = lead.country_id or lead.partner_id.country_id
            expected_prefix = lead._get_customer_id_prefix(country)
            current_code = lead.generated_customer_id or ''
            if not current_code or not current_code.startswith(f'{expected_prefix}-'):
                lead.generated_customer_id = lead._generate_customer_id(
                    prefix=expected_prefix
                )

    @api.model
    def _is_saudi_country(self, country):
        return bool(country and (country.code == 'SA' or country.name == 'Saudi Arabia'))

    @api.model
    def _get_customer_id_prefix(self, country=False):
        return '01' if self._is_saudi_country(country) else '02'

    @api.model
    def _get_customer_id_prefix_from_vals(self, vals):
        country = self.env['res.country'].browse()
        if vals.get('country_id'):
            country = self.env['res.country'].browse(vals['country_id']).exists()
        elif vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id']).exists()
            country = partner.country_id
        return self._get_customer_id_prefix(country)

    @api.model
    def _generate_customer_id(self, country=False, prefix=False, offset=0):
        prefix = prefix or self._get_customer_id_prefix(country)
        return self.env['res.partner']._get_next_customer_code(
            country=country,
            prefix=prefix,
            offset=offset,
        )

    def _compute_requirement_form_count(self):
        grouped_data = self.env['crm.requirement.form'].read_group(
            [('lead_id', 'in', self.ids)],
            ['lead_id'],
            ['lead_id'],
        )
        count_by_lead = {
            item['lead_id'][0]: item['lead_id_count'] for item in grouped_data
        }
        for lead in self:
            lead.requirement_form_count = count_by_lead.get(lead.id, 0)

    def _compute_customer_rating_count(self):
        grouped_data = self.env['crm.customer.rating'].read_group(
            [('lead_id', 'in', self.ids)],
            ['lead_id'],
            ['lead_id'],
        )
        count_by_lead = {
            item['lead_id'][0]: item['lead_id_count'] for item in grouped_data
        }
        for lead in self:
            lead.customer_rating_count = count_by_lead.get(lead.id, 0)

    @api.depends('partner_id', 'customer_rating_count')
    def _compute_customer_rating_rank(self):
        rating_model = self.env['crm.customer.rating']
        partner_ids = self.mapped('partner_id').ids
        ratings = rating_model.search([
            '|',
            ('partner_id', 'in', partner_ids or [0]),
            ('lead_id', 'in', self.ids or [0]),
        ])

        weights_by_partner = {}
        weights_by_lead = {}
        for rating in ratings:
            weight = rating_model._rank_to_weight(rating.rank)
            if not weight:
                continue
            if rating.partner_id:
                weights_by_partner.setdefault(rating.partner_id.id, []).append(weight)
            weights_by_lead.setdefault(rating.lead_id.id, []).append(weight)

        for lead in self:
            if lead.partner_id:
                weights = weights_by_partner.get(lead.partner_id.id, [])
            else:
                weights = weights_by_lead.get(lead.id, [])
            lead.customer_rating_rank = (
                rating_model._rank_from_average(sum(weights) / len(weights))
                if weights
                else False
            )

    def _get_optional_field_value(self, record, field_name):
        if record and field_name in record._fields:
            return record[field_name]
        return False

    def _get_requirement_customer_values(self):
        self.ensure_one()
        partner = self.partner_id
        invoice_partner = partner.child_ids.filtered(
            lambda child: child.type == 'invoice'
        )[:1]
        billing_partner = invoice_partner or partner

        country = (
            billing_partner.country_id
            or partner.country_id
            or self.country_id
        )
        state = billing_partner.state_id or partner.state_id or self.state_id

        customer_name = partner.name or self.partner_name or self.name or ''
        customer_short_name = (
            partner.commercial_partner_id.ref or self.customer_short_name or ''
        )
        contact_person = self.contact_name or partner.name or ''
        contact_number = (
            self._get_optional_field_value(self, 'phone')
            or self._get_optional_field_value(self, 'mobile')
            or self._get_optional_field_value(partner, 'phone')
            or self._get_optional_field_value(partner, 'mobile')
            or ''
        )
        customer_email = self.email_from or partner.email or ''
        if not self.generated_customer_id:
            self.generated_customer_id = self._generate_customer_id(country=country)

        return {
            'from_crm': True,
            'lead_id': self.id,
            'partner_id': partner.id if partner else False,
            'user_id': self.user_id.id or self.env.user.id,
            'customer_name': customer_name,
            'customer_short_name': customer_short_name,
            'customer_id': self.generated_customer_id or '',
            'customer_email': customer_email,
            'contact_person': contact_person,
            'contact_number': contact_number,
            'whatsapp_number': (
                partner.whatsapp_number
                if partner and partner.whatsapp_number
                else self.whatsapp_number or ''
            ),
            'business_licence': self.business_licence or '',
            'vat_no': partner.commercial_partner_id.vat or self.vat_no or '',
            'address_street': billing_partner.street or partner.street or self.street or '',
            'address_city': billing_partner.city or partner.city or self.city or '',
            'address_state': state.id if state else False,
            'address_country': country.id if country else False,
            'postal_code': billing_partner.zip or partner.zip or self.zip or '',
            'local_export': (
                'local'
                if self._is_saudi_country(country)
                else 'export'
            ),
            'payment_terms': (
                str(partner.property_payment_term_id.id)
                if partner and 'property_payment_term_id' in partner._fields
                and partner.property_payment_term_id
                else False
            ),
        }

    def action_open_requirement_form(self):
        self.ensure_one()
        if self.type != 'opportunity':
            raise UserError(
                _(
                    'Please convert the Lead to an Opportunity first, '
                    'then fill up the Requirement Form.'
                )
            )
        if not self.generated_customer_id:
            country = self.country_id or self.partner_id.country_id
            self.generated_customer_id = self._generate_customer_id(country=country)

        existing = self.env['crm.requirement.form'].search([
            ('lead_id', '=', self.id),
        ], limit=1)

        if existing:
            sync_values = {}
            if existing.business_licence != (self.business_licence or False):
                sync_values['business_licence'] = self.business_licence or False
            expected_user = self.user_id or self.env.user
            if existing.user_id != expected_user:
                sync_values['user_id'] = expected_user.id
            if sync_values:
                existing.write(sync_values)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Requirement Form',
                'res_model': 'crm.requirement.form',
                'view_mode': 'form',
                'view_id': self.env.ref(
                    'crm_requirement_form.crm_requirement_form_form'
                ).id,
                'res_id': existing.id,
                'target': 'current',
                'context': {'form_view_initial_mode': 'edit'},
            }

        requirement = self.env['crm.requirement.form'].create(
            self._get_requirement_customer_values()
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Requirement Form',
            'res_model': 'crm.requirement.form',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'crm_requirement_form.crm_requirement_form_form'
            ).id,
            'res_id': requirement.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_view_requirement_forms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Requirement Forms',
            'res_model': 'crm.requirement.form',
            'view_mode': 'list,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }

    def action_open_customer_rating(self):
        self.ensure_one()
        rating = self.env['crm.customer.rating'].search([
            ('lead_id', '=', self.id),
        ], limit=1)
        if not rating:
            rating = self.env['crm.customer.rating'].create({'lead_id': self.id})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Ranking',
            'res_model': 'crm.customer.rating',
            'view_mode': 'form',
            'res_id': rating.id,
            'target': 'current',
        }
