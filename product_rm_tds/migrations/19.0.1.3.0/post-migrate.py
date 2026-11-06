from odoo import SUPERUSER_ID, api


def _number(text):
    try:
        return float(str(text).strip())
    except (ValueError, TypeError):
        return None


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    physical = env['product.rm.tds.physical.line'].with_context(active_test=False)
    quality = env['product.rm.tds.quality.line'].with_context(active_test=False)
    texts = env['product.rm.tds.text.line'].with_context(active_test=False)

    for line in physical.search([('property', 'in', ['web_width', 'thickness'])]):
        if line.value_integer and not line.value_float:
            line.value_float = float(line.value_integer)

    for line in texts.search([]):
        number = _number(line.value_text)
        if number is not None and not line.value_float:
            line.value_float = number

    # Move old options to the correct category, preserving legacy text.
    for source in physical.search([('property', '=', 'substrate_grade')]):
        existing = texts.search([
            ('product_tmpl_id', '=', source.product_tmpl_id.id),
            ('property', '=', 'substrate_grade'),
            ('value_text', '=', source.value_text or False),
        ], limit=1)
        if not existing:
            number = _number(source.value_text)
            texts.create({
                'product_tmpl_id': source.product_tmpl_id.id,
                'sequence': source.sequence,
                'property': 'substrate_grade',
                'value_float': number if number is not None else 0.0,
                'value_text': source.value_text,
            })
        source.unlink()

    for source in quality.search([
        ('property', 'in', ['treatment_surface', 'treatment_reverse'])
    ]):
        existing = texts.search([
            ('product_tmpl_id', '=', source.product_tmpl_id.id),
            ('property', '=', source.property),
            ('value_text', '=', source.value_text or False),
        ], limit=1)
        if not existing:
            number = _number(source.value_text)
            texts.create({
                'product_tmpl_id': source.product_tmpl_id.id,
                'sequence': source.sequence,
                'property': source.property,
                'value_float': number if number is not None else source.value_float,
                'value_text': source.value_text,
            })
        source.unlink()
