from collections import defaultdict

from odoo import models, fields, api, _


class StockLot(models.Model):
    _inherit = 'stock.lot'

    related_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Related Vendor',
        compute='_compute_related_vendor_ids',
        help=(
            'Vendors linked to completed supplier receipts for this '
            'lot/serial number.'
        ),
    )

    @api.depends('name')
    def _compute_related_vendor_ids(self):
        vendors_by_lot = defaultdict(set)

        if self.ids:
            move_lines = self.env['stock.move.line'].search([
                ('lot_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('location_id.usage', '=', 'supplier'),
                ('picking_id.partner_id', '!=', False),
            ])
            for move_line in move_lines:
                vendors_by_lot[move_line.lot_id.id].add(
                    move_line.picking_id.partner_id.id
                )

        Partner = self.env['res.partner']
        for lot in self:
            lot.related_vendor_ids = Partner.browse(
                vendors_by_lot.get(lot.id, set())
            )
