from odoo import models, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rm_qc_check_ids = fields.One2many(
        'quality.check', 'picking_id', string='QC Inspections')

    def action_rm_qc_create_checks(self):
        """Create one check for each QC-required product and received lot.

        Explicit receipt action only: no fake automatic stock blocking or release.
        Historic QCS-linked checks are reused rather than duplicated.
        """
        Check = self.env['quality.check']
        test_type = self.env['quality.point.test_type'].search([
            ('technical_name', '=', 'passfail')], limit=1)
        if not test_type:
            raise UserError(_('The standard Pass - Fail Quality test type is missing.'))
        for picking in self:
            if picking.picking_type_id.code != 'incoming':
                raise UserError(_('Use QC Inspection only on incoming receipts.'))
            candidates = []
            for move in picking.move_ids.filtered(
                    lambda m: m.product_id.rm_qc_required):
                lots = move.move_line_ids.mapped('lot_id')
                candidates.extend((move.product_id, lot) for lot in lots)
                if not lots:
                    candidates.append((move.product_id, False))
            seen = set()
            for product, lot in candidates:
                key = (product.id, lot.id if lot else False)
                if key in seen:
                    continue
                seen.add(key)
                existing = Check.search([
                    ('picking_id', '=', picking.id),
                    ('product_id', '=', product.id),
                    ('rm_qc_scope', '=', 'incoming'),
                    ('lot_ids', 'in', [lot.id]) if lot else ('lot_ids', '=', False),
                    '|', ('rm_qc_is_custom', '=', True),
                         ('rm_qc_specification_id', '!=', False),
                ], limit=1)
                if existing:
                    continue
                # Validate that master test rules exist before creating anything.
                self.env['rm.qc.parameter.template'].applicable_to(
                    product, scope='incoming')
                vals = {
                    'title': _('Incoming QC: %s') % product.display_name,
                    'product_id': product.id,
                    'picking_id': picking.id,
                    'lot_ids': [fields.Command.set([lot.id])] if lot else [],
                    'test_type_id': test_type.id,
                    'measure_on': 'product',
                    'rm_qc_scope': 'incoming',
                    'rm_qc_is_custom': True,
                    'company_id': picking.company_id.id,
                }
                check = Check.create(vals)
                check.action_rm_qc_load_tests()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receipt QC Inspections'),
            'res_model': 'quality.check',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_list').id,
                 'list'),
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_quality_check_form').id,
                 'form'),
            ],
            'domain': [('picking_id', 'in', self.ids),
                       '|', ('rm_qc_is_custom', '=', True),
                            ('rm_qc_specification_id', '!=', False)],
            'context': {'default_rm_qc_scope': 'incoming'},
        }
