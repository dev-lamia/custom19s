from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    artwork_sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        compute='_compute_artwork_sale_order_id',
        store=True,
        readonly=True,
        index=True,
        copy=False,
        help='Sales Order linked to the artwork task in this project.',
    )
    artwork_sale_order_ref = fields.Char(
        related='artwork_sale_order_id.name',
        string='Sales Order Reference',
        readonly=True,
        store=True,
    )

    @api.depends('task_ids.artwork_sale_order_id')
    def _compute_artwork_sale_order_id(self):
        for project in self:
            artwork_tasks = project.task_ids.filtered(
                lambda task: task.artwork_sale_order_id
            )
            project.artwork_sale_order_id = (
                artwork_tasks[:1].artwork_sale_order_id
                if artwork_tasks
                else False
            )
