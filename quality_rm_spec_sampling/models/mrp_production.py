from odoo import models, fields, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    rm_qc_check_ids = fields.One2many('quality.check', 'rm_qc_production_id',
                                     string='Production QC Check Logs')

    def action_rm_qc_create_production_checks(self):
        """Stage-wise QC under quality.check; no manufacturing blocking rule imposed."""
        Check = self.env['quality.check']
        test_type = self.env['quality.point.test_type'].search(
            [('technical_name', '=', 'passfail')], limit=1)
        if not test_type:
            raise UserError(_('The standard Pass - Fail Quality test type is missing.'))
        Spec = self.env['rm.qc.specification']
        for order in self:
            specs = Spec.with_company(order.company_id).search([
                ('product_tmpl_id', '=', order.product_id.product_tmpl_id.id),
                ('scope', '=', 'production'), ('state', '=', 'approved'),
                ('company_id', '=', order.company_id.id),
            ], order='approved_on desc, id desc')
            unique_stages = set()
            for spec in specs:
                stage = spec.process or 'Production'
                if stage in unique_stages:
                    continue
                unique_stages.add(stage)
                existing = Check.search([
                    ('rm_qc_production_id', '=', order.id),
                    ('rm_qc_stage', '=', stage),
                ], limit=1)
                if existing:
                    continue
                vals = {
                    'title': _('Production QC — %s: %s') % (order.name, stage),
                    'product_id': order.product_id.id,
                    'test_type_id': test_type.id,
                    'measure_on': 'product',
                    'company_id': order.company_id.id,
                    'rm_qc_scope': 'production',
                    'rm_qc_stage': stage,
                    'rm_qc_production_id': order.id,
                    'rm_qc_specification_id': spec.id,
                }
                # The native manufacturing link exists when installed integrations provide it.
                if 'production_id' in Check._fields:
                    vals['production_id'] = order.id
                check = Check.create(vals)
                check.action_rm_qc_load_specification()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'quality.check',
            'name': _('Production QC Checks'), 'view_mode': 'list,form',
            'views': [
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_list').id, 'list'),
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_form').id, 'form'),
            ],
            'domain': [('rm_qc_production_id', 'in', self.ids)],
        }
