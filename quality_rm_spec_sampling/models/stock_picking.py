from odoo import models, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rm_qc_check_ids = fields.One2many('quality.check', 'picking_id', string='Quality Checks')

    def action_rm_qc_create_checks(self):
        """Run from any receipt, including Done. Never modifies stock quantities."""
        QualityCheck = self.env['quality.check']
        test_type = self.env['quality.point.test_type'].search(
            [('technical_name', '=', 'passfail')], limit=1)
        if not test_type:
            raise UserError(_('The standard Pass - Fail Quality test type is missing.'))
        Specification = self.env['rm.qc.specification']
        created = QualityCheck.browse()
        for picking in self:
            if picking.picking_type_id.code != 'incoming':
                raise UserError(_('RM QC checks can only be generated from incoming receipts.'))
            # get move lines with assigned batches, plus non-lot products
            rows = []
            for move in picking.move_ids.filtered(lambda m: m.product_id.rm_qc_required):
                lines = move.move_line_ids.filtered(lambda m: m.lot_id)
                if lines:
                    rows.extend([(move.product_id, ml.lot_id) for ml in lines])
                else:
                    rows.append((move.product_id, False))
            seen = set()
            for product, lot in rows:
                key = (product.id, lot.id if lot else False)
                if key in seen:
                    continue
                seen.add(key)
                spec = Specification.with_company(picking.company_id)._find_approved(product)
                if not spec:
                    raise UserError(_('QC Manager confirmed specification missing for %s.')
                                    % product.display_name)
                existing = QualityCheck.search([
                    ('picking_id', '=', picking.id), ('product_id', '=', product.id),
                    (('lot_ids', 'in', [lot.id]) if lot else ('lot_ids', '=', False)),
                    ('rm_qc_specification_id', '=', spec.id),
                ], limit=1)
                if existing:
                    continue
                vals = {
                    'title': _('RM Incoming QC: %s') % product.display_name,
                    'product_id': product.id, 'picking_id': picking.id,
                    'lot_ids': [fields.Command.set([lot.id])] if lot else [],
                    'test_type_id': test_type.id,
                    'measure_on': 'product',
                    'rm_qc_scope': 'incoming',
                    'rm_qc_specification_id': spec.id,
                    'company_id': picking.company_id.id,
                }
                check = QualityCheck.create(vals)
                check.action_rm_qc_load_specification()
                created |= check
        return {
            'type': 'ir.actions.act_window',
            'name': _('Incoming RM Quality Checks'),
            'res_model': 'quality.check',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_list').id, 'list'),
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_form').id, 'form'),
            ],
            'domain': [('picking_id', 'in', self.ids)],
            'context': {'default_rm_qc_scope': 'incoming'},
        }
