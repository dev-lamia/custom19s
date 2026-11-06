from odoo import SUPERUSER_ID, api


LEGACY_MODELS = {
    'product.rm.tds.physical.line': ('product_rm_tds_physical_line', {
        'web_width': 'rm_prop_web_width',
        'thickness': 'rm_prop_thickness',
        'density': 'rm_prop_density',
        'optical_density': 'rm_prop_optical_density',
        'radial_crush': 'rm_prop_radial_crush',
    }),
    'product.rm.tds.text.line': ('product_rm_tds_text_line', {
        'substrate_grade': 'rm_prop_substrate_grade',
        'treatment_surface': 'rm_prop_treatment_surface',
        'treatment_reverse': 'rm_prop_treatment_reverse',
    }),
    'product.rm.tds.quality.line': ('product_rm_tds_quality_line', {
        'wvtr': 'rm_prop_wvtr',
        'otr': 'rm_prop_otr',
        'cof_rating': 'rm_prop_cof_rating',
        'solid_content': 'rm_prop_solid_content',
        'max_moisture': 'rm_prop_max_moisture',
    }),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name, (table, mapping) in LEGACY_MODELS.items():
        cr.execute("""SELECT 1 FROM information_schema.columns
                       WHERE table_schema = current_schema()
                         AND table_name = %s AND column_name = 'property' """, (table,))
        if not cr.fetchone():
            continue
        model = env[model_name].sudo()
        for old_key, xml_id in mapping.items():
            prop = env.ref('product_rm_tds.%s' % xml_id, raise_if_not_found=False)
            if not prop:
                continue
            cr.execute(
                'UPDATE "' + table + '" SET property_id = %s '
                'WHERE property = %s AND property_id IS NULL',
                (prop.id, old_key),
            )
        model.invalidate_model(['property_id'])
