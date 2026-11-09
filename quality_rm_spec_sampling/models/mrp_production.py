from odoo import models, fields, api, _
from odoo.exceptions import UserError


STAGES = [
    ('Pre-Press Setup', 'Pre-Press Setup'),
    ('Live Press Run', 'Live Press Run'),
    ('Post-Print QC', 'Post-Print QC'),
    ('Lamination', 'Lamination'),
    ('Slitting', 'Slitting'),
    ('Pouch Making', 'Pouch Making'),
    ('Valving', 'Valving'),
]


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    rm_qc_check_ids = fields.One2many(
        'quality.check', 'rm_qc_production_id', string='Production QC Checks')

    def action_rm_qc_create_production_checks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Choose a Production QC Stage'),
            'res_model': 'rm.qc.production.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_id': self.id},
        }


class ProductionStageWizard(models.TransientModel):
    _name = 'rm.qc.production.stage.wizard'
    _description = 'Select Production Quality Check Stage'

    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order', required=True)
    stage = fields.Selection(STAGES, string='Production Stage', required=True)

    def action_open_check(self):
        self.ensure_one()
        order = self.production_id
        Test = self.env['rm.qc.parameter.template']
        Check = self.env['quality.check']
        existing = Check.search([
            ('rm_qc_production_id', '=', order.id),
            ('rm_qc_stage', '=', self.stage),
            '|', ('rm_qc_is_custom', '=', True),
                 ('rm_qc_specification_id', '!=', False),
        ], limit=1)
        if not existing:
            Test.applicable_to(order.product_id, 'production', self.stage)
            test_type = self.env['quality.point.test_type'].search([
                ('technical_name', '=', 'passfail')], limit=1)
            if not test_type:
                raise UserError(_('The Pass - Fail Quality test type is missing.'))
            values = {
                'title': _('Production QC: %s — %s') % (order.name, self.stage),
                'product_id': order.product_id.id,
                'test_type_id': test_type.id,
                'measure_on': 'product',
                'company_id': order.company_id.id,
                'rm_qc_is_custom': True,
                'rm_qc_scope': 'production',
                'rm_qc_stage': self.stage,
                'rm_qc_production_id': order.id,
            }
            if 'production_id' in Check._fields:
                values['production_id'] = order.id
            existing = Check.create(values)
            existing.action_rm_qc_load_tests()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Production QC'),
            'res_model': 'quality.check',
            'res_id': existing.id,
            'view_mode': 'form',
            'views': [(
                self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_form').id,
                'form')],
            'target': 'current',
        }
