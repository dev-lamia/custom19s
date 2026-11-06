from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    artwork_task_ids = fields.One2many(
        'project.task',
        'artwork_sale_order_id',
        string='Artwork Tasks',
        copy=False,
    )
    artwork_task_count = fields.Integer(
        string='Artwork',
        compute='_compute_artwork_task_count',
    )

    @api.depends('artwork_task_ids')
    def _compute_artwork_task_count(self):
        for order in self:
            order.artwork_task_count = len(order.artwork_task_ids)

    can_create_artwork = fields.Boolean(
        string='Can Create Artwork',
        compute='_compute_can_create_artwork',
    )

    @api.depends('state', 'invoice_ids.state', 'invoice_ids.move_type')
    def _compute_can_create_artwork(self):
        for order in self:
            valid_invoices = order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.state == 'posted'
            )
            order.can_create_artwork = order.state == 'sale' and bool(valid_invoices)

    def action_create_artwork(self):
        self.ensure_one()
        if self.state != 'sale':
            raise ValidationError(
                _('Artwork can only be created after the Sales Order is confirmed.')
            )

        job_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.job_code
        )
        if not job_lines:
            raise ValidationError(
                _('No Sales Order line with a Job Code was found.')
            )

        if self.artwork_task_ids:
            return self.action_open_artwork()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Artwork Projects'),
            'res_model': 'artwork.project.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def action_open_artwork(self):
        self.ensure_one()
        tasks = self.artwork_task_ids
        if not tasks:
            return self.action_create_artwork()

        projects = tasks.mapped('project_id')
        if len(projects) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Artwork Project'),
                'res_model': 'project.project',
                'view_mode': 'form',
                'res_id': projects.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Artwork Projects'),
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', projects.ids)],
            'context': {'create': False},
            'target': 'current',
        }
