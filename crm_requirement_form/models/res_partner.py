from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_code = fields.Char(
        string='Customer Code',
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help='Customer code shared with CRM generated customer IDs.',
    )
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        tracking=True,
        help='Primary WhatsApp number synchronized with CRM and Requirement Forms.',
    )

    def _register_hook(self):
        """Repair missing WhatsApp columns before HTTP requests are served."""
        for table_name in (
            'res_partner',
            'crm_lead',
            'crm_requirement_form',
        ):
            self.env.cr.execute(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name = %s
                   AND column_name = 'whatsapp_number'
                """,
                (table_name,),
            )
            if not self.env.cr.fetchone():
                # table_name comes only from the fixed whitelist above.
                self.env.cr.execute(
                    f'ALTER TABLE IF EXISTS {table_name} '
                    'ADD COLUMN whatsapp_number VARCHAR'
                )
        return super()._register_hook()

    requirement_form_count = fields.Integer(
        string='Requirement Forms',
        compute='_compute_requirement_form_count',
    )

    customer_rating_count = fields.Integer(
        string='Customer Rankings',
        compute='_compute_customer_rating_count',
    )

    requirement_document_attachment_ids = fields.Many2many(
        'ir.attachment',
        'res_partner_requirement_document_attachment_rel',
        'partner_id',
        'attachment_id',
        string='Requirement Documents',
        copy=False,
        help='Documents collected from CRM Requirement Forms for this customer.',
    )

    @api.depends('child_ids')
    def _compute_requirement_form_count(self):
        Requirement = self.env['crm.requirement.form']
        for partner in self:
            commercial_partner = partner.commercial_partner_id
            partner.requirement_form_count = Requirement.search_count([
                '|',
                ('partner_id.commercial_partner_id', '=', commercial_partner.id),
                ('lead_id.partner_id.commercial_partner_id', '=', commercial_partner.id),
            ]) if commercial_partner else 0

    def action_view_requirement_forms(self):
        self.ensure_one()
        commercial_partner = self.commercial_partner_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requirement Forms'),
            'res_model': 'crm.requirement.form',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('partner_id.commercial_partner_id', '=', commercial_partner.id),
                ('lead_id.partner_id.commercial_partner_id', '=', commercial_partner.id),
            ],
            'context': {'default_partner_id': commercial_partner.id},
        }


    @api.depends('child_ids')
    def _compute_customer_rating_count(self):
        commercial_partners = self.mapped('commercial_partner_id')
        counts = {partner.id: 0 for partner in commercial_partners}
        if commercial_partners:
            ratings = self.env['crm.customer.rating'].search([
                ('partner_id.commercial_partner_id', 'in', commercial_partners.ids),
            ])
            for rating in ratings:
                commercial_partner = rating.partner_id.commercial_partner_id
                if commercial_partner:
                    counts[commercial_partner.id] = (
                        counts.get(commercial_partner.id, 0) + 1
                    )

        for partner in self:
            commercial_partner = partner.commercial_partner_id
            partner.customer_rating_count = counts.get(
                commercial_partner.id, 0
            ) if commercial_partner else 0

    def action_view_customer_rankings(self):
        self.ensure_one()
        commercial_partner = self.commercial_partner_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Rankings'),
            'res_model': 'crm.customer.rating',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id.commercial_partner_id', '=', commercial_partner.id),
            ],
            'context': {
                'default_partner_id': commercial_partner.id,
                'default_lead_id': False,
            },
            'target': 'current',
        }

    @api.constrains('ref', 'parent_id')
    def _check_customer_short_name_unique(self):
        for partner in self:
            if partner.parent_id:
                continue
            short_name = (partner.ref or '').strip()
            if not short_name:
                continue

            if self.sudo().search_count([
                ('id', '!=', partner.id),
                ('parent_id', '=', False),
                ('ref', '=ilike', short_name),
            ]):
                raise ValidationError(
                    _('Customer Short Name must be unique. "%s" is already used by another customer.')
                    % short_name
                )


    @api.onchange('ref')
    def _onchange_customer_short_name_unique_warning(self):
        for partner in self:
            if partner.parent_id:
                continue
            short_name = (partner.ref or '').strip()
            if not short_name:
                continue
            domain = [
                ('parent_id', '=', False),
                ('ref', '=ilike', short_name),
            ]
            if partner._origin.id:
                domain.append(('id', '!=', partner._origin.id))
            if self.sudo().search_count(domain):
                return {
                    'warning': {
                        'title': _('Customer Short Name Must Be Unique'),
                        'message': _('The Customer Short Name "%s" is already used by another customer. Please enter a unique short name.') % short_name,
                    }
                }
        return {}

    def _get_requirement_supplier_initial(self):
        """Return the fixed supplier prefix used by raw-material Item Codes.

        The current business rule defines Supplier Initial as 02 for all
        purchase item codes, so no database field is required on res.partner.
        """
        self.ensure_one()
        return '02'

    @api.model
    def _is_saudi_country(self, country):
        return bool(country and (country.code == 'SA' or country.name == 'Saudi Arabia'))

    @api.model
    def _get_customer_code_prefix(self, country=False):
        return '01' if self._is_saudi_country(country) else '02'

    @api.model
    def _get_next_customer_code(self, country=False, prefix=False, offset=0):
        """Return the next code from the shared CRM/Contacts numbering pool."""
        prefix = prefix or self._get_customer_code_prefix(country)
        code_prefix = f'{prefix}-'

        partner_codes = self.search([
            ('customer_code', '=like', f'{code_prefix}%'),
        ]).mapped('customer_code')
        lead_codes = self.env['crm.lead'].search([
            ('generated_customer_id', '=like', f'{code_prefix}%'),
        ]).mapped('generated_customer_id')

        serials = []
        for code in set(partner_codes + lead_codes):
            if not code or not code.startswith(code_prefix):
                continue
            serial_part = code[len(code_prefix):]
            if serial_part.isdigit():
                serials.append(int(serial_part))

        next_serial = (max(serials) if serials else 0) + 1 + offset
        return f'{prefix}-{next_serial:05d}'

    @api.model
    def _is_supplier_creation(self, vals):
        """Return whether a partner is being created as a vendor/supplier."""
        context = self.env.context
        supplier_rank = vals.get('supplier_rank', 0) or 0
        default_supplier_rank = context.get('default_supplier_rank', 0) or 0
        return bool(
            supplier_rank > 0
            or default_supplier_rank > 0
            or context.get('res_partner_search_mode') == 'supplier'
        )

    @api.model
    def _is_managed_customer_code(self, code):
        """Return True for Customer Codes generated by this module."""
        return bool(code and (code.startswith('01-') or code.startswith('02-')))

    def _ensure_customer_code_for_sales(self, country=False):
        """Return a Customer Code for a partner explicitly used in Sales.

        Vendor creation itself must not generate a Customer Code.  This helper
        is intentionally called only from the Requirement Form / Sale Order
        customer flow, where the same partner is being used as a sales customer.
        """
        self.ensure_one()
        partner = self.commercial_partner_id
        if not partner:
            return False

        customer_code = (partner.customer_code or '').strip()
        if customer_code:
            return customer_code

        country = country or partner.country_id
        customer_code = partner._get_next_customer_code(country=country)
        partner.with_context(
            skip_supplier_customer_code_cleanup=True,
            skip_customer_code_country_sync=True,
        ).write({'customer_code': customer_code})
        return customer_code

    def _filter_supplier_only_partners(self):
        """Return suppliers that have not been used in the sales customer flow."""
        candidates = self.filtered(lambda partner: partner.supplier_rank > 0)
        if not candidates:
            return candidates

        commercial_ids = candidates.mapped('commercial_partner_id').ids
        used_ids = set(
            self.env['sale.order'].search([
                ('partner_id.commercial_partner_id', 'in', commercial_ids),
            ]).mapped('partner_id.commercial_partner_id').ids
        )
        opportunity_partners = self.env['crm.lead'].search([
            ('type', '=', 'opportunity'),
            ('partner_id.commercial_partner_id', 'in', commercial_ids),
        ]).mapped('partner_id.commercial_partner_id')
        used_ids.update(opportunity_partners.ids)

        requirement_forms = self.env['crm.requirement.form'].search([
            '|',
            ('partner_id.commercial_partner_id', 'in', commercial_ids),
            ('lead_id.partner_id.commercial_partner_id', 'in', commercial_ids),
        ])
        used_ids.update(
            requirement_forms.mapped('partner_id.commercial_partner_id').ids
        )
        used_ids.update(
            requirement_forms.mapped(
                'lead_id.partner_id.commercial_partner_id'
            ).ids
        )

        return candidates.filtered(
            lambda partner: partner.customer_rank <= 0
            and partner.commercial_partner_id.id not in used_ids
        )

    def init(self):
        """Remove legacy auto-generated Customer Codes from existing vendors."""
        suppliers = self.search([
            ('supplier_rank', '>', 0),
            ('customer_code', '!=', False),
        ])._filter_supplier_only_partners()
        suppliers = suppliers.filtered(
            lambda partner: self._is_managed_customer_code(partner.customer_code)
        )
        if suppliers:
            suppliers.with_context(
                skip_supplier_customer_code_cleanup=True,
                skip_customer_code_country_sync=True,
            ).write({'customer_code': False})

    @api.model_create_multi
    def create(self, vals_list):
        prefix_offsets = {}
        for vals in vals_list:
            # Child/contact addresses belong to the commercial customer and do not
            # receive an independent customer code. Vendor creation can initially
            # arrive with supplier_rank=0, so the vendor action context must also
            # be checked before assigning a Customer Code.
            if (
                vals.get('parent_id')
                or vals.get('customer_code')
                or self._is_supplier_creation(vals)
            ):
                continue

            country = self.env['res.country'].browse()
            if vals.get('country_id'):
                country = self.env['res.country'].browse(vals['country_id']).exists()

            prefix = self._get_customer_code_prefix(country)
            offset = prefix_offsets.get(prefix, 0)
            vals['customer_code'] = self._get_next_customer_code(
                country=country,
                prefix=prefix,
                offset=offset,
            )
            prefix_offsets[prefix] = offset + 1

        partners = super().create(vals_list)

        # Odoo can increase supplier_rank after the initial partner creation.
        # Remove only module-generated codes from records that are suppliers.
        suppliers_with_code = partners._filter_supplier_only_partners().filtered(
            lambda partner: self._is_managed_customer_code(partner.customer_code)
        )
        if suppliers_with_code:
            suppliers_with_code.with_context(
                skip_supplier_customer_code_cleanup=True,
                skip_customer_code_country_sync=True,
            ).write({'customer_code': False})

        return partners

    def _sync_whatsapp_to_related_records(self):
        """Propagate Contact WhatsApp changes to CRM and Requirement Forms."""
        if self.env.context.get('skip_whatsapp_related_sync'):
            return

        Lead = self.env['crm.lead']
        Requirement = self.env['crm.requirement.form']
        for partner in self:
            leads = Lead.search([('partner_id', '=', partner.id)])
            if leads:
                leads.with_context(
                    skip_whatsapp_partner_sync=True,
                ).write({
                    'whatsapp_number': partner.whatsapp_number or False,
                })

            requirements = Requirement.search([
                '|',
                ('partner_id', '=', partner.id),
                ('lead_id.partner_id', '=', partner.id),
            ])
            if requirements:
                requirements.with_context(
                    skip_whatsapp_partner_sync=True,
                ).write({
                    'whatsapp_number': partner.whatsapp_number or False,
                })

    def _sync_short_name_to_related_records(self):
        """Propagate Customer Short Name (ref) to CRM records and Requirement Forms."""
        Lead = self.env['crm.lead']
        Requirement = self.env['crm.requirement.form']
        for partner in self.mapped('commercial_partner_id'):
            if partner.parent_id:
                continue
            name = (partner.ref or '').strip() or False

            leads = Lead.search([
                ('partner_id.commercial_partner_id', '=', partner.id),
            ]).filtered(lambda lead: (lead.customer_short_name or False) != name)
            if leads:
                leads.with_context(skip_short_name_partner_sync=True).write({
                    'customer_short_name': name,
                })

            requirements = Requirement.search([
                '|',
                ('partner_id.commercial_partner_id', '=', partner.id),
                ('lead_id.partner_id.commercial_partner_id', '=', partner.id),
            ]).filtered(lambda form: (form.customer_short_name or False) != name)
            if requirements:
                requirements.with_context(skip_short_name_partner_sync=True).write({
                    'customer_short_name': name,
                })

    def _sync_vat_to_related_records(self):
        """Propagate Contact VAT (Tax ID) to CRM records and Requirement Forms."""
        Lead = self.env['crm.lead']
        Requirement = self.env['crm.requirement.form']
        for partner in self.mapped('commercial_partner_id'):
            vat = partner.vat or False

            leads = Lead.search([
                ('partner_id.commercial_partner_id', '=', partner.id),
            ]).filtered(lambda lead: (lead.vat_no or False) != vat)
            if leads:
                leads.with_context(skip_vat_partner_sync=True).write({
                    'vat_no': vat,
                })

            requirements = Requirement.search([
                '|',
                ('partner_id.commercial_partner_id', '=', partner.id),
                ('lead_id.partner_id.commercial_partner_id', '=', partner.id),
            ]).filtered(lambda form: (form.vat_no or False) != vat)
            if requirements:
                requirements.with_context(skip_vat_partner_sync=True).write({
                    'vat_no': vat,
                })

    def write(self, vals):
        """Keep the customer-code prefix aligned with the partner country.

        Saudi Arabia uses 01-xxxxx and every other country uses 02-xxxxx.
        An explicitly supplied customer_code (for example from CRM sync) is
        preserved. Child contacts do not receive an independent code.
        """
        if self.env.context.get('skip_customer_code_country_sync'):
            result = super().write(vals)
            if 'whatsapp_number' in vals:
                self._sync_whatsapp_to_related_records()
            if 'vat' in vals and not self.env.context.get('skip_vat_related_sync'):
                self._sync_vat_to_related_records()
            if 'ref' in vals and not self.env.context.get('skip_short_name_related_sync'):
                self.filtered(lambda p: not p.parent_id)._sync_short_name_to_related_records()
            return result

        result = super().write(vals)

        if 'whatsapp_number' in vals:
            self._sync_whatsapp_to_related_records()

        if 'vat' in vals and not self.env.context.get('skip_vat_related_sync'):
            self._sync_vat_to_related_records()

        if 'ref' in vals and not self.env.context.get('skip_short_name_related_sync'):
            self.filtered(lambda p: not p.parent_id)._sync_short_name_to_related_records()

        # When Odoo promotes a partner to vendor status after creation, clear any
        # Customer Code previously generated by this module. Manual/legacy codes
        # with another format are preserved.
        if not self.env.context.get('skip_supplier_customer_code_cleanup'):
            suppliers_with_code = self._filter_supplier_only_partners().filtered(
                lambda partner: self._is_managed_customer_code(partner.customer_code)
            )
            if suppliers_with_code:
                suppliers_with_code.with_context(
                    skip_supplier_customer_code_cleanup=True,
                    skip_customer_code_country_sync=True,
                ).write({'customer_code': False})

        if (
            'industry_id' in vals
            and not self.env.context.get('skip_industry_lead_sync')
        ):
            commercial_partners = self.mapped('commercial_partner_id')
            if commercial_partners:
                leads = self.env['crm.lead'].search([
                    (
                        'partner_id.commercial_partner_id',
                        'in',
                        commercial_partners.ids,
                    ),
                ])
                if leads:
                    leads.with_context(skip_industry_partner_sync=True).write({
                        'industry_category_id': vals.get('industry_id') or False,
                    })

        if 'country_id' not in vals or 'customer_code' in vals:
            return result

        prefix_offsets = {}
        for partner in self.filtered(
            lambda rec: not rec.parent_id and rec.supplier_rank <= 0
        ):
            expected_prefix = partner._get_customer_code_prefix(partner.country_id)
            current_code = partner.customer_code or ''

            # Only replace codes managed by this module. This avoids touching
            # any legacy/manual customer reference with another format.
            managed_code = (
                not current_code
                or current_code.startswith('01-')
                or current_code.startswith('02-')
            )
            if managed_code and not current_code.startswith(f'{expected_prefix}-'):
                offset = prefix_offsets.get(expected_prefix, 0)
                new_code = partner._get_next_customer_code(
                    country=partner.country_id,
                    prefix=expected_prefix,
                    offset=offset,
                )
                prefix_offsets[expected_prefix] = offset + 1
                partner.with_context(skip_customer_code_country_sync=True).write({
                    'customer_code': new_code,
                })

        return result
