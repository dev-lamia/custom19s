from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    products = env['product.template'].with_context(active_test=False).search([])
    physical = env['product.rm.tds.physical.line']
    quality = env['product.rm.tds.quality.line']
    texts = env['product.rm.tds.text.line']
    numeric_fields = {
        'rm_tds_web_width': ('web_width', 'value_integer'),
        'rm_tds_thickness': ('thickness', 'value_integer'),
        'rm_tds_density': ('density', 'value_float'),
        'rm_tds_optical_density': ('optical_density', 'value_float'),
        'rm_tds_radial_crush': ('radial_crush', 'value_float'),
    }
    percentage_fields = {
        'rm_tds_wvtr': 'wvtr', 'rm_tds_otr': 'otr',
        'rm_tds_cof_rating': 'cof_rating',
        'rm_tds_solid_content': 'solid_content',
        'rm_tds_max_moisture': 'max_moisture',
    }
    text_fields = {
        'rm_tds_substrate_grade': 'substrate_grade',
        'rm_tds_treatment_surface': 'treatment_surface',
        'rm_tds_treatment_reverse': 'treatment_reverse',
    }
    for product in products:
        for field_name, (prop, val_field) in numeric_fields.items():
            value = product[field_name]
            if value and not physical.search_count([
                ('product_tmpl_id', '=', product.id), ('property', '=', prop),
                (val_field, '=', value),
            ]):
                physical.create({'product_tmpl_id': product.id, 'property': prop, val_field: value})
        for field_name, prop in percentage_fields.items():
            value = product[field_name]
            if value and not quality.search_count([
                ('product_tmpl_id', '=', product.id), ('property', '=', prop),
                ('value_float', '=', value),
            ]):
                quality.create({'product_tmpl_id': product.id, 'property': prop, 'value_float': value})
        for field_name, prop in text_fields.items():
            value = product[field_name]
            if value and not texts.search_count([
                ('product_tmpl_id', '=', product.id), ('property', '=', prop),
                ('value_text', '=', value),
            ]):
                texts.create({'product_tmpl_id': product.id, 'property': prop, 'value_text': value})
    for line in physical.search([('property', '=', 'substrate_grade')]):
        if line.value_text and not texts.search_count([
            ('product_tmpl_id', '=', line.product_tmpl_id.id),
            ('property', '=', 'substrate_grade'), ('value_text', '=', line.value_text),
        ]):
            texts.create({'product_tmpl_id': line.product_tmpl_id.id, 'property': 'substrate_grade', 'value_text': line.value_text})
    for line in quality.search([('property', 'in', ['treatment_surface', 'treatment_reverse'])]):
        if line.value_text and not texts.search_count([
            ('product_tmpl_id', '=', line.product_tmpl_id.id),
            ('property', '=', line.property), ('value_text', '=', line.value_text),
        ]):
            texts.create({'product_tmpl_id': line.product_tmpl_id.id, 'property': line.property, 'value_text': line.value_text})
