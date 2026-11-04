from markupsafe import Markup

from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    artwork_sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        copy=False,
        readonly=True,
        index=True,
        ondelete='set null',
    )
    artwork_sale_order_ref = fields.Char(
        related='artwork_sale_order_id.name',
        string='Sales Order Reference',
        readonly=True,
        store=True,
    )
    artwork_sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Line',
        copy=False,
        readonly=True,
        index=True,
        ondelete='set null',
    )
    artwork_gdn_number_link = fields.Html(
        string='GDN Number',
        compute='_compute_artwork_links',
        readonly=True,
        sanitize=False,
    )
    artwork_job_code_link = fields.Html(
        string='Job Code',
        compute='_compute_artwork_links',
        readonly=True,
        sanitize=False,
    )

    @api.depends(
        'artwork_sale_order_line_id.job_code',
        'artwork_sale_order_line_id.gdn_number',
        'artwork_sale_order_line_id.gdn_configuration_id',
    )
    def _compute_artwork_links(self):
        for task in self:
            line = task.artwork_sale_order_line_id
            task.artwork_job_code_link = False
            task.artwork_gdn_number_link = False

            if line and line.job_code and isinstance(line.id, int):
                task.artwork_job_code_link = Markup(
                    '<a href="/web#id=%s&amp;model=sale.job.code.configuration'
                    '&amp;view_type=form" class="fw-semibold">%s</a>'
                    % (line.id, line.job_code)
                )

            if line and line.gdn_number and line.gdn_configuration_id:
                task.artwork_gdn_number_link = Markup(
                    '<a href="/web#id=%s&amp;model=sale.gdn.configuration'
                    '&amp;view_type=form" class="fw-semibold">%s</a>'
                    % (line.gdn_configuration_id.id, line.gdn_number)
                )


    def action_open_artwork_sale_order(self):
        self.ensure_one()
        if not self.artwork_sale_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.artwork_sale_order_id.id,
            'target': 'current',
        }
