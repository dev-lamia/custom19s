import base64
import re

from odoo import http
from odoo.http import request


class RequirementFormController(http.Controller):

    def _get_form_by_token(self, token):
        token = (token or '').strip()
        if not token:
            return request.env['crm.requirement.form'].sudo().browse()

        Form = request.env['crm.requirement.form'].sudo()
        form = Form.search([('token', '=', token)], limit=1)
        if form:
            return form

        return Form.search([
            ('public_url', 'ilike', '/requirement/form/%s' % token),
        ], limit=1)

    def _get_previous_requirement_domain(self, form):
        """Return requirement forms that can be reused for a repeat job.

        A repeat job can reference any earlier requirement form by REQ ID.  Do
        not restrict the lookup to the current lead/customer because repeat
        jobs are often created from a new CRM lead while reusing an older REQ.
        The current form itself is always excluded.
        """
        return [
            ('id', '!=', form.id),
            ('name', '!=', 'New'),
            ('specification_ids', '!=', False),
        ]

    def _get_previous_requirement_forms(self, form):
        return request.env['crm.requirement.form'].sudo().search(
            self._get_previous_requirement_domain(form),
            order='id desc',
            limit=500,
        )

    def _serialize_repeat_specification(self, specification):
        bag_product = specification.bag_type_product_tmpl_id
        bag_code = (
            bag_product.requirement_bag_type_code or ''
        ).strip().upper() if bag_product else ''

        fg_type = specification.fg_type or 'bag'
        if bag_code in {'RS', 'LBL'}:
            fg_type = 'roll'

        roll_type = specification.roll_type
        if fg_type == 'roll' and not roll_type:
            roll_type = 'label' if bag_code == 'LBL' else 'roll'

        print_finish = specification.print_finish_id
        if not print_finish and specification.print_finish_ids:
            print_finish = specification.print_finish_ids[:1]

        data = {
            'design_name': specification.design_name or '',
            'design_dimension_uom': specification.design_dimension_uom or 'mm',
            'color_reference': specification.color_reference or '',
            'color_reference_type': specification.color_reference_type or '',
            'quantity': specification.quantity or 0,
            'quantity_uom_id': specification.quantity_uom_id.id or '',
            'fg_type': fg_type,
            'roll_type': roll_type or '',
            'bag_type_product_tmpl_id': (
                bag_product.id if bag_product else ''
            ),
            'length': specification.length or 0,
            'width': specification.width or 0,
            'gusset': specification.gusset or 0,
            'coil_width_mm': specification.coil_width_mm or 0,
            'cutoff_length_mm': specification.cutoff_length_mm or 0,
            'final_roll_direction': specification.final_roll_direction or '',
            'final_roll_weight_kg': specification.final_roll_weight_kg or 0,
            'final_roll_od_mm': specification.final_roll_od_mm or 0,
            'final_roll_meters': specification.final_roll_meters or 0,
            'core_id_mm': specification.core_id_mm or 0,
            'core_thickness_mm': specification.core_thickness_mm or 0,
            'core_type': specification.core_type or '',
            'print_finish_id': print_finish.id if print_finish else '',
            'standard_feature_ids': [
                str(option_id)
                for option_id in specification.standard_feature_ids.ids
            ],
            'additional_requirements': (
                specification.additional_requirements or ''
            ),
        }

        for layer_no in range(1, 11):
            product = specification[
                f'layer_{layer_no}_product_tmpl_id'
            ]
            variant = specification[f'layer_{layer_no}_variant_id']
            data[f'layer_{layer_no}_product_tmpl_id'] = (
                product.id if product else ''
            )
            data[f'layer_{layer_no}_variant_id'] = (
                variant.id if variant else ''
            )
            data[f'layer_{layer_no}_thickness'] = (
                specification[f'layer_{layer_no}_thickness'] or 0
            )

        return data

    def _get_product_context(self):
        ProductTemplate = request.env['product.template'].sudo()
        ProductVariant = request.env['product.product'].sudo()
        PaymentTerm = request.env['account.payment.term'].sudo()
        PrintFinishOption = request.env['crm.requirement.print.finish.option'].sudo()
        FeatureOption = request.env['crm.requirement.feature.option'].sudo()
        Uom = request.env['uom.uom'].sudo()

        product_templates = ProductTemplate.search(
            [
                ('active', '=', True),
                ('is_requirement_layer', '=', True),
            ],
            order='name, id',
            limit=1000,
        )
        product_variants = ProductVariant.search(
            [
                ('active', '=', True),
                ('product_tmpl_id', 'in', product_templates.ids),
            ],
            order='product_tmpl_id, name, id',
            limit=3000,
        )
        fg_products = ProductTemplate.search(
            [
                ('active', '=', True),
                ('requirement_fg_type', 'in', ['bag', 'roll']),
            ],
            order='name, id',
        )
        return {
            'product_templates': product_templates,
            'product_variants': product_variants,
            'payment_terms': PaymentTerm.search([], order='name, id'),
            'print_finish_options': PrintFinishOption.search(
                [('active', '=', True)], order='sequence, name, id'
            ),
            'feature_options': FeatureOption.search(
                [('active', '=', True)], order='sequence, name, id'
            ),
            'fg_products': fg_products,
            'quantity_uoms': Uom.search(
                [('active', '=', True)],
                order='name, id',
            ),
        }

    def _to_float(self, val):
        try:
            return max(float(val), 0.0) if val else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _to_int(self, val):
        try:
            return max(int(val), 0) if val else 0
        except (TypeError, ValueError):
            return 0

    def _get_record(self, model_name, value):
        record_id = self._to_int(value)
        if not record_id:
            return request.env[model_name].sudo().browse()
        return request.env[model_name].sudo().browse(record_id).exists()

    def _get_records(self, model_name, values):
        if isinstance(values, str):
            values = [values]
        record_ids = [self._to_int(value) for value in (values or [])]
        record_ids = [record_id for record_id in record_ids if record_id]
        if not record_ids:
            return request.env[model_name].sudo().browse()
        return request.env[model_name].sudo().browse(record_ids).exists()

    def _create_uploaded_documents(self, form):
        files = []
        allowed_field_names = {
            'document_files',
            'document_files[]',
            'saudi_document_files',
            'saudi_document_files[]',
            'saudi_document_cr',
            'saudi_document_vat',
            'saudi_document_address',
            'saudi_document_bank',
        }
        uploaded_files = request.httprequest.files
        for field_name in uploaded_files.keys():
            if field_name in allowed_field_names or field_name.startswith('saudi_document_'):
                files.extend(uploaded_files.getlist(field_name))

        if not files:
            return

        Attachment = request.env['ir.attachment'].sudo()
        commands = []
        for upload in files:
            filename = (upload.filename or '').strip()
            if not filename:
                continue
            content = upload.read()
            if not content:
                continue
            target = form.partner_id or form
            attachment_values = {
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(content).decode('ascii'),
                'res_model': target._name,
                'res_id': target.id,
                'mimetype': upload.mimetype or 'application/octet-stream',
            }
            if 'public' in Attachment._fields:
                attachment_values['public'] = True
            attachment = Attachment.create(attachment_values)
            commands.append((4, attachment.id))

        if commands:
            if form.partner_id:
                form.partner_id.write({
                    'requirement_document_attachment_ids': commands,
                })
            else:
                form.write({'document_attachment_ids': commands})

    def _layer_values(self, data, layer_no):
        tmpl = self._get_record(
            'product.template', data.get(f'layer_{layer_no}_product_tmpl_id')
        )
        variant = self._get_record(
            'product.product', data.get(f'layer_{layer_no}_variant_id')
        )

        if tmpl and not tmpl.is_requirement_layer:
            tmpl = request.env['product.template'].sudo().browse()
            variant = request.env['product.product'].sudo().browse()

        if variant and not variant.product_tmpl_id.is_requirement_layer:
            variant = request.env['product.product'].sudo().browse()

        if variant and tmpl and variant.product_tmpl_id != tmpl:
            variant = request.env['product.product'].sudo().browse()

        material = tmpl.display_name if tmpl else False
        thickness = tmpl.thickness_microns if tmpl else 0.0
        variant = request.env['product.product'].sudo().browse()

        return {
            f'layer_{layer_no}_product_tmpl_id': tmpl.id if tmpl else False,
            f'layer_{layer_no}_variant_id': variant.id if variant else False,
            f'layer_{layer_no}_material': material or '',
            f'layer_{layer_no}_thickness': thickness,
        }

    @http.route(
        '/requirement/form/internal/<int:form_id>',
        type='http',
        auth='user',
        website=True,
    )
    def internal_requirement_form(self, form_id, **kwargs):
        form = request.env['crm.requirement.form'].search([
            ('id', '=', form_id),
        ], limit=1)
        if not form:
            return request.render(
                'crm_requirement_form.requirement_form_not_found_page', {}
            )

        # The website template and its AJAX/submit endpoints use the token.
        # Generate it silently for internal usage; the user never has to open
        # or copy a public link.
        form._ensure_public_customer_link()

        if form.state == 'submitted':
            return request.render(
                'crm_requirement_form.requirement_form_readonly_page',
                {'form': form, 'internal_embed': True},
            )

        values = {
            'form': form,
            'previous_requirement_forms': self._get_previous_requirement_forms(form),
            'internal_embed': True,
            'internal_saved': False,
        }
        values.update(self._get_product_context())
        return request.render('crm_requirement_form.requirement_form_page', values)

    @http.route('/requirement/form/<string:token>', type='http', auth='public', website=True)
    def requirement_form(self, token=None, **kwargs):
        form = self._get_form_by_token(token)
        if not form:
            return request.render('crm_requirement_form.requirement_form_not_found_page', {})

        if form.state == 'submitted':
            return request.render(
                'crm_requirement_form.requirement_form_readonly_page',
                {'form': form},
            )

        values = {
            'form': form,
            'previous_requirement_forms': self._get_previous_requirement_forms(form),
            'internal_embed': False,
        }
        values.update(self._get_product_context())
        return request.render('crm_requirement_form.requirement_form_page', values)

    @http.route(
        '/requirement/form/previous-data/<string:token>',
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        csrf=False,
    )
    def previous_requirement_data(self, token=None, req_id=None, **kwargs):
        form = self._get_form_by_token(token)
        if not form:
            return request.make_json_response(
                {'ok': False, 'message': 'Requirement form not found.'},
                status=404,
            )

        req_id = (req_id or '').strip()
        if not req_id:
            return request.make_json_response(
                {'ok': False, 'message': 'Previous REQ ID is required.'},
                status=400,
            )

        domain = self._get_previous_requirement_domain(form) + [
            ('name', '=ilike', req_id),
        ]
        previous_form = request.env['crm.requirement.form'].sudo().search(
            domain,
            order='id desc',
            limit=1,
        )
        if not previous_form:
            return request.make_json_response(
                {
                    'ok': False,
                    'message': (
                        'No submitted previous requirement was found for this '
                        'customer with that REQ ID.'
                    ),
                },
                status=404,
            )

        specifications = previous_form.specification_ids.sorted(
            key=lambda specification: (specification.sequence, specification.id)
        )
        return request.make_json_response({
            'ok': True,
            'req_id': previous_form.name,
            'specifications': [
                self._serialize_repeat_specification(specification)
                for specification in specifications
            ],
        })

    @http.route(
        '/requirement/form/submit/<string:token>',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False,
    )
    def submit_requirement_form(self, token=None, **post):
        form = self._get_form_by_token(token)
        if not form:
            return request.render('crm_requirement_form.requirement_form_not_found_page', {})
        if form.state == 'submitted':
            return request.render(
                'crm_requirement_form.requirement_form_readonly_page',
                {'form': form},
            )

        http_form = request.httprequest.form
        internal_embed = bool(http_form.get('internal_embed'))
        internal_save = internal_embed and bool(http_form.get('internal_save'))
        contract_type = http_form.get('contract_type') or False
        payment_term = self._get_record(
            'account.payment.term', http_form.get('payment_term_id')
        )

        # The backend Product Specifications tab intentionally posts only
        # product-specification inputs. Preserve customer/commercial fields
        # that are not rendered in the internal iframe instead of clearing
        # them on submit.
        form_values = {
            'new_job': bool(http_form.get('new_job')),
            'repeat_job': (
                bool(http_form.get('repeat_job'))
                and not bool(http_form.get('new_job'))
            ),
        }
        if not internal_save:
            form_values['state'] = 'submitted'
        if not internal_embed:
            form_values.update({
                'title': http_form.get('title') or False,
                'vat_no': http_form.get('vat_no') or False,
                'payment_terms': str(payment_term.id) if payment_term else False,
                'delivery_terms': http_form.get('delivery_terms') or False,
                'contract_type': contract_type,
                'contract_duration': (
                    self._to_int(http_form.get('contract_duration'))
                    if contract_type == 'long_term_supply'
                    else 0
                ),
                'port': http_form.get('port') or False,
                'local_export': http_form.get('local_export') or False,
                'requirement_details': (
                    http_form.get('requirement_details') or False
                ),
            })
        form.write(form_values)

        specs_data = {}
        pattern = re.compile(r'^spec\[(\d+)]\[(\w+)]$')
        multi_fields = {'standard_feature_ids'}

        for key in http_form.keys():
            match = pattern.match(key)
            if not match:
                continue
            idx = int(match.group(1))
            field = match.group(2)
            specs_data.setdefault(idx, {})[field] = (
                http_form.getlist(key) if field in multi_fields else http_form.get(key)
            )

        if not internal_embed:
            self._create_uploaded_documents(form)

        form.specification_ids.unlink()
        Specification = request.env['crm.requirement.specification'].sudo()
        ProductTemplate = request.env['product.template'].sudo()
        for idx in sorted(specs_data):
            data = specs_data[idx]
            print_finish_option = self._get_record(
                'crm.requirement.print.finish.option',
                data.get('print_finish_id'),
            )
            feature_options = self._get_records(
                'crm.requirement.feature.option',
                data.get('standard_feature_ids') or [],
            )
            fg_type = (
                data.get('fg_type')
                if data.get('fg_type') in {'bag', 'roll'}
                else 'bag'
            )
            roll_type = False
            quantity_uom = self._get_record(
                'uom.uom', data.get('quantity_uom_id')
            )
            if quantity_uom and not quantity_uom.active:
                quantity_uom = request.env['uom.uom'].sudo().browse()

            bag_type_product = self._get_record(
                'product.template', data.get('bag_type_product_tmpl_id')
            )
            if (
                bag_type_product
                and bag_type_product.requirement_fg_type != fg_type
            ):
                bag_type_product = ProductTemplate.browse()

            if bag_type_product and fg_type == 'roll':
                bag_code = (
                    bag_type_product.requirement_bag_type_code or ''
                ).strip().upper()
                roll_type = 'label' if bag_code == 'LBL' else 'roll'

            legacy_uom = False
            if quantity_uom:
                normalized_uom = (quantity_uom.name or '').strip().upper()
                if normalized_uom in {'PCS', 'PC', 'PCE', 'UNIT', 'UNITS'}:
                    legacy_uom = 'pcs'
                elif normalized_uom in {'KG', 'KGS', 'KILOGRAM', 'KILOGRAMS'}:
                    legacy_uom = 'kg'
                elif normalized_uom in {'LM', 'LINEAR METER', 'LINEAR METERS'}:
                    legacy_uom = 'lm'

            feature_codes = set(feature_options.mapped('code'))

            has_valve_c = 'valve_c_type' in feature_codes
            has_valve_s = 'valve_s_type' in feature_codes
            has_valve = has_valve_c or has_valve_s
            valve_type = 'c' if has_valve_c else ('s' if has_valve_s else False)

            values = {
                'form_id': form.id,
                'sequence': idx + 1,
                'previous_req_form': (
                    data.get('previous_req_form') or False
                    if form.repeat_job
                    else False
                ),
                'design_name': data.get('design_name') or '',
                'design_dimension_uom': (
                    data.get('design_dimension_uom')
                    if data.get('design_dimension_uom') in {'mm', 'cm', 'inch', 'meters'}
                    else 'mm'
                ),
                'no_designs': idx + 1,
                'color_reference': data.get('color_reference') or False,
                'color_reference_type': (
                    data.get('color_reference_type')
                    if data.get('color_reference') == 'yes'
                    else False
                ),
                'quantity': self._to_int(data.get('quantity')),
                'quantity_uom': legacy_uom,
                'quantity_uom_id': quantity_uom.id if quantity_uom else False,
                'fg_type': fg_type,
                'roll_type': roll_type,
                'bag_type_product_tmpl_id': (
                    bag_type_product.id if bag_type_product else False
                ),
                'bag_type': (
                    bag_type_product.display_name
                    if bag_type_product
                    else data.get('bag_type') or False
                ),
                'length': (
                    self._to_float(data.get('length')) if fg_type == 'bag' else 0.0
                ),
                'width': (
                    self._to_int(data.get('width')) if fg_type == 'bag' else 0
                ),
                'gusset': (
                    0.0
                    if (
                        fg_type == 'roll'
                        or (
                            bag_type_product
                            and bag_type_product._requirement_should_hide_gusset()
                        )
                    )
                    else self._to_float(data.get('gusset'))
                ),
                'coil_width_mm': (
                    self._to_float(data.get('coil_width_mm'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'cutoff_length_mm': (
                    self._to_float(data.get('cutoff_length_mm'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'final_roll_direction': (
                    (data.get('final_roll_direction') or '').strip()
                    if fg_type == 'roll'
                    else False
                ),
                'final_roll_weight_kg': (
                    self._to_float(data.get('final_roll_weight_kg'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'final_roll_od_mm': (
                    self._to_float(data.get('final_roll_od_mm'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'final_roll_meters': (
                    self._to_float(data.get('final_roll_meters'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'core_id_mm': (
                    self._to_float(data.get('core_id_mm'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'core_thickness_mm': (
                    self._to_float(data.get('core_thickness_mm'))
                    if fg_type == 'roll'
                    else 0.0
                ),
                'core_type': (
                    (data.get('core_type') or '').strip()
                    if fg_type == 'roll'
                    else False
                ),
                'print_finish_ids': [(6, 0, print_finish_option.ids)],
                'standard_feature_ids': [(6, 0, feature_options.ids)],
                'print_finish': print_finish_option.name or False,
                'standard_features': ', '.join(feature_options.mapped('name')),
                'feature_tear_notch_zipper': 'tear_notch' in feature_codes,
                'feature_rounded_corners': bool(
                    {'rounded_corner_punch', 'rounded_corner_diecut'} & feature_codes
                ),
                'valve': has_valve,
                'valve_type': valve_type,
                'feature_other_note': False,
                'back_if_yes': data.get('back_if_yes') if has_valve else False,
                'additional_requirements': data.get('additional_requirements') or '',
            }
            for layer_no in range(1, 11):
                values.update(self._layer_values(data, layer_no))

            values['material'] = ', '.join(filter(None, [
                values.get(f'layer_{layer_no}_material')
                for layer_no in range(1, 11)
            ]))
            values['thickness'] = sum(
                values.get(f'layer_{layer_no}_thickness', 0.0)
                for layer_no in range(1, 11)
            )

            Specification.create(values)

        if internal_embed and internal_save:
            values = {
                'form': form,
                'previous_requirement_forms': self._get_previous_requirement_forms(form),
                'internal_embed': True,
                'internal_saved': True,
            }
            values.update(self._get_product_context())
            return request.render(
                'crm_requirement_form.requirement_form_page', values
            )

        if internal_embed:
            return request.render(
                'crm_requirement_form.requirement_form_readonly_page',
                {'form': form, 'internal_embed': True},
            )
        return request.render(
            'crm_requirement_form.requirement_form_thanks', {'form': form}
        )
