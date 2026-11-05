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
        """Resolve Repeat Jobs to artwork on their original design/Sales Order.

        The new customer may differ from the original customer.  Follow the
        Requirement Form source-specification chain first rather than applying
        a same-customer restriction or assigning new artwork ownership.
        """
        Task = self.env['project.task']
        result = {order.id: order.artwork_task_ids for order in self}
        repeat_orders = self.filtered(lambda order: order.repeat_job)
        if not repeat_orders:
            return result

        # Group source references per order and job code.  Include every
        # ancestor to support repeat-of-repeat and designs with multiple SOs.
        source_by_order = {}
        all_source_lines = set()
        all_source_orders = set()
        all_codes = set()
        for order in repeat_orders:
            sources = {}
            for line in order.order_line:
                if line.display_type or not line.job_code:
                    continue
                code = line.job_code.strip()
                if not code:
                    continue
                all_codes.add(code)
                source_line_ids, source_order_ids = sources.setdefault(
                    code, (set(), set())
                )
                spec = line.requirement_specification_id
                ancestor = spec.source_specification_id if spec else False
                visited = set()
                while ancestor and ancestor.id not in visited:
                    visited.add(ancestor.id)
                    for previous_line in ancestor.sale_order_line_ids:
                        if (previous_line.display_type
                                or (previous_line.job_code or '').strip() != code):
                            continue
                        source_line_ids.add(previous_line.id)
                        source_order_ids.add(previous_line.order_id.id)
                    ancestor = ancestor.source_specification_id
            source_by_order[order.id] = sources
            for line_ids, order_ids in sources.values():
                all_source_lines.update(line_ids)
                all_source_orders.update(order_ids)

        if not all_codes:
            return result

        # The exact source sale lines are authoritative; Job Code alone is a
        # fallback for older records with incomplete specification references.
        domain = [
            '|',
            ('artwork_sale_order_line_id', 'in', sorted(all_source_lines)),
            ('artwork_sale_order_line_id.job_code', 'in', sorted(all_codes)),
        ]
        candidates = Task.search(domain)
        if all_source_orders:
            # Legacy tasks can have the original SO but no SO-line reference.
            candidates |= Task.search([
                ('artwork_sale_order_id', 'in', sorted(all_source_orders)),
            ])

        for order in repeat_orders:
            for code, (source_line_ids, source_order_ids) in (
                source_by_order[order.id].items()
            ):
                # Prefer artwork linked to the original specification line.
                matched = candidates.filtered(
                    lambda task: task.artwork_sale_order_line_id.id
                    in source_line_ids
                )
                if not matched and source_order_ids:
                    matched = candidates.filtered(
                        lambda task: task.artwork_sale_order_id.id
                        in source_order_ids
                        and (task.name or '').strip() == code
                    )

                if not matched:
                    # Fallback for older Repeat Jobs whose source-specification
                    # link is missing. Never restrict by customer: CRM explicitly
                    # allows reuse of another customer's original design.
                    fallback = candidates.filtered(
                        lambda task: (
                            task.artwork_sale_order_id != order
                            and task.artwork_sale_order_id.company_id == order.company_id
                            and task.artwork_sale_order_line_id
                            and (task.artwork_sale_order_line_id.job_code or '').strip()
                            == code
                        )
                    )
                    # Prefer the earliest created project if legacy data has
                    # more than one artwork carrying the same Job Code.
                    matched = fallback.sorted(key=lambda task: task.id)[:1]

                result[order.id] |= matched

        return result

    @api.depends(
        'artwork_task_ids', 'repeat_job', 'order_line.job_code',
        'order_line.display_type', 'order_line.requirement_specification_id',
        'partner_id', 'company_id',
        'order_line.requirement_specification_id.source_specification_id',
    )
    def _compute_artwork_task_count(self):
        task_map = self._get_artwork_tasks_by_order()
        for order in self:
            order.artwork_task_count = len(task_map[order.id])

    can_create_artwork = fields.Boolean(
        string='Can Create Artwork',
        compute='_compute_can_create_artwork',
    )

    @api.depends(
        'state', 'invoice_ids.state', 'invoice_ids.move_type',
        'artwork_task_ids',
    )
    def _compute_can_create_artwork(self):
        for order in self:
            valid_invoices = order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.state == 'posted'
            )
            # Repeat Jobs may already show artwork linked from a previous SO.
            # Block duplicates only for tasks created by this specific SO.
            order.can_create_artwork = (
                order.state == 'sale'
                and bool(valid_invoices)
                and not order.artwork_task_ids
            )

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
