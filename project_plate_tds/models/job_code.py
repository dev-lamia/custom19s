
from odoo import api, fields, models, _


class JobCodeConfiguration(models.Model):
    _inherit = 'sale.job.code.configuration'

    plate_tds_count = fields.Integer(
        string='Plate TDS Count',
        compute='_compute_plate_tds_count',
    )

    def _compute_plate_tds_count(self):
        for rec in self:
            rec.plate_tds_count = self.env['plate.tds'].search_count([
                ('sale_line_id', '=', rec.source_line_id.id)
            ])

    def action_open_plate_tds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Plate Technical Data Sheets'),
            'res_model': 'plate.tds',
            'view_mode': 'list,form',
            'domain': [('sale_line_id', '=', self.source_line_id.id)],
            'context': {'create': False},
        }
