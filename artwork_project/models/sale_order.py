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

    def _get_artwork_tasks_by_order(self):
        """Return own artwork, or the original artwork reused by a Repeat Job.

        Artwork tasks always belong to their original Sales Order and Job Code;
        repeating a Job does not create or reassign any project or task.
        """
        Task = self.env['project.task']
        result = {order.id: order.artwork_task_ids for order in self}
        repeat_orders = self.filtered(lambda order: order.repeat_job)
        if not repeat_orders:
            return result

        job_codes = {
            line.job_code.strip()
            for order in repeat_orders
            for line in order.order_line
            if not line.display_type and line.job_code
            and line.job_code.strip()
        }
        if not job_codes:
            return result

        # Restrict matching to the same commercial customer and company.
        # One query covers all Repeat Job orders in the recordset.
        candidates = Task.search([
            ('artwork_sale_order_line_id.job_code', 'in', sorted(job_codes)),
            ('artwork_sale_order_id.company_id', 'in',
             repeat_orders.mapped('company_id').ids),
            ('artwork_sale_order_id.partner_id.commercial_partner_id', 'in',
             repeat_orders.mapped('partner_id.commercial_partner_id').ids),
        ])

        for order in repeat_orders:
            customer = order.partner_id.commercial_partner_id
            available = candidates.filtered(
                lambda task: task.artwork_sale_order_id.company_id == order.company_id
                and task.artwork_sale_order_id.partner_id.commercial_partner_id == customer
                and task.artwork_sale_order_id != order
            )
            reused = Task
            for line in order.order_line.filtered(
                lambda item: not item.display_type and item.job_code
            ):
                code = line.job_code.strip()
                matched = available.filtered(
                    lambda task: task.artwork_sale_order_line_id.job_code.strip() == code
                )
                if not matched:
                    continue

                # Prefer the artwork for this design's actual previous
                # Requirement Form, including repeat-of-repeat chains.
                source_ids = set()
                specification = line.requirement_specification_id
                source = (specification.source_specification_id
                          if specification else False)
                while source and source.id not in source_ids:
                    source_ids.add(source.id)
                    source = source.source_specification_id
                if source_ids:
                    source_matched = matched.filtered(
                        lambda task: task.artwork_sale_order_line_id
                        .requirement_specification_id.id in source_ids
                    )
                    if source_matched:
                        matched = source_matched

                reused |= matched

            # Preserve any pre-existing artwork directly attached to the SO.
            result[order.id] |= reused

        return result

    @api.depends(
        'artwork_task_ids', 'repeat_job', 'order_line.job_code',
        'order_line.display_type', 'order_line.requirement_specification_id',
        'partner_id', 'company_id',
    )
    def _compute_artwork_task_count(self):
        task_map = self._get_artwork_tasks_by_order()
        for order in self:
            order.artwork_task_count = len(task_map[order.id])

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
        if self.repeat_job:
            raise ValidationError(
                _('Artwork can only be created for New Job sales orders.')
            )
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
        tasks = self._get_artwork_tasks_by_order()[self.id]
        if not tasks:
            if self.repeat_job:
                raise ValidationError(_(
                    'No existing Artwork was found for this Repeat Job.'
                ))
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
