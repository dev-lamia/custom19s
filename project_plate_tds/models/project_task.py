from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    plate_tds_ids = fields.One2many('plate.tds', 'task_id', string='Plate TDS')
    plate_tds_count = fields.Integer(compute='_compute_plate_tds_count', string='TDS Count')

    @api.depends('plate_tds_ids')
    def _compute_plate_tds_count(self):
        for task in self:
            task.plate_tds_count = len(task.plate_tds_ids)

    def action_generate_plate_tds(self):
        self.ensure_one()
        line = self.artwork_sale_order_line_id
        if not line or not line.gdn_configuration_id:
            raise UserError(_('This task has no linked GDN. Add a GDN to its Sales Order Line first.'))
        if self.plate_tds_ids:
            return self.action_open_plate_tds()
        values = self.env['plate.tds']._prepare_from_task(self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Plate TDS'),
            'res_model': 'plate.tds',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_' + key: value for key, value in values.items()},
        }

    def action_open_plate_tds(self):
        self.ensure_one()
        records = self.plate_tds_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Plate Technical Data Sheets'),
            'res_model': 'plate.tds',
            'view_mode': 'list,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }
        if len(records) == 1:
            action.update(view_mode='form', res_id=records.id)
        return action
