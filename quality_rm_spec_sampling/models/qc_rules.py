"""QC rules are sourced from the configurable master, not a TDS document."""
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


NUMBER = re.compile(r'^\s*([+-]?\d+(?:\.\d+)?)\s*%?\s*$')
NOMINAL = re.compile(
    r'^\s*Nominal\s*([+-])\s*(\d+(?:\.\d+)?)\s*(%)?\s*$', re.I
)


def number_or_none(raw):
    match = NUMBER.fullmatch(str(raw or ''))
    return float(match.group(1)) if match else None


def resolved_limit(text, nominal=None):
    direct = number_or_none(text)
    if direct is not None:
        return direct
    match = NOMINAL.fullmatch(str(text or ''))
    if not match or nominal is None:
        return None
    diff = float(match.group(2))
    if match.group(3):
        diff = nominal * diff / 100
    return nominal + diff if match.group(1) == '+' else nominal - diff


def default_samples(rule):
    match = re.match(r'^\s*(\d+)\s+', rule or '')
    return min(int(match.group(1)), 1000) if match else 1


class RmQcParameterTemplateRules(models.Model):
    _inherit = 'rm.qc.parameter.template'

    @api.model
    def applicable_to(self, product, scope='incoming', stage=None):
        """The source workbook's material and stage rules determine the tests."""
        domain = [('scope', '=', scope), ('active', '=', True)]
        if scope == 'incoming':
            material_type = product.product_tmpl_id.rm_qc_material_type
            if not material_type:
                raise UserError(_(
                    'Set the Material Type in the product RM Quality tab first.'
                ))
            domain.append(('material_type', '=', material_type))
        elif scope == 'production':
            if not stage:
                raise UserError(_('Select the production stage first.'))
            domain.append(('process', '=', stage))
        else:
            raise UserError(_('Unknown inspection scope.'))
        rules = self.search(domain, order='sequence, id')
        if scope == 'incoming' and product.product_tmpl_id.rm_qc_material_type == 'film':
            grade = (product.product_tmpl_id.rm_qc_film_type or '').upper()
            if not grade:
                raise UserError(_('Choose the Film Grade on the product first.'))
            rules = rules.filtered(lambda r: bool(re.search(
                r'\b%s\b' % re.escape(grade), (r.item_text or '').upper()
            )))
        if not rules:
            raise UserError(_(
                'No QC tests are configured for %(product)s (%(scope)s). '
                'Review RM Quality > Configuration > QC Test Rules.'
            ) % {'product': product.display_name,
                 'scope': stage if scope == 'production' else scope})
        return rules

    def _nominal_value_for(self, product):
        """Only match a genuinely corresponding product property, never guess."""
        self.ensure_one()
        name = (self.name or '').lower()
        if 'thickness' in name or 'caliper' in name:
            wanted = {'thickness / gauge'}
        elif 'grammage' in name or 'basis weight' in name:
            wanted = {'grammage / basis weight', 'basis weight', 'grammage'}
        else:
            wanted = set()
        for prop in product.product_tmpl_id.rm_qc_identification_line_ids:
            if prop.name.strip().lower() in wanted:
                return number_or_none(prop.value)
        return None

    def inspection_commands(self, product):
        """Snapshot reference limits, sampling and evaluation settings on each check."""
        commands = []
        for rule in self:
            nominal = rule._nominal_value_for(product)
            lower = resolved_limit(rule.lsl_text, nominal)
            upper = resolved_limit(rule.usl_text, nominal)
            numeric = lower is not None and upper is not None and lower <= upper
            commands.append(fields.Command.create({
                'master_parameter_id': rule.id,
                'name': rule.name,
                'uom_text': rule.uom_text,
                'lsl_text': rule.lsl_text,
                'target_text': rule.target_text,
                'usl_text': rule.usl_text,
                'limit_mode': 'numeric' if numeric else 'reference',
                'lsl_numeric': lower if numeric else 0,
                'usl_numeric': upper if numeric else 0,
                'inspection_method': rule.inspection_method,
                'lot_size': rule.lot_size,
                'sample_size': rule.sample_size,
                'samples_to_test': default_samples(rule.sample_size),
                'measurements_per_sample': rule.measurements_per_sample,
                'sample_method': rule.sample_method,
                'inspection_level': rule.inspection_level,
                'inspection_frequency': rule.inspection_frequency,
            }))
        return commands
