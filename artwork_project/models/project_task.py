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
    artwork_latest_sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        compute='_compute_artwork_latest_sale_order',
        readonly=True,
        help=(
            'Latest confirmed Repeat Job Sales Order for this artwork, '
            'or the original Sales Order when there is no confirmed repeat.'
        ),
    )
    artwork_latest_sale_order_ref = fields.Char(
        string='Sales Order Reference',
        related='artwork_latest_sale_order_id.name',
        readonly=True,
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


    @api.depends(
        'artwork_sale_order_id',
        'artwork_sale_order_line_id',
        'artwork_sale_order_line_id.job_code',
        'artwork_sale_order_line_id.requirement_specification_id',
        'artwork_sale_order_line_id.gdn_configuration_id',
    )
    def _compute_artwork_latest_sale_order(self):
        """Show latest confirmed repeat SO without changing artwork ownership.

        The original artwork_sale_order_id remains the ownership reference
        used by the original order's artwork One2many and project records.
        A repeat job reuses that task, so its latest SO is display-only.
        """
        codes = set()
        companies = set()
        for task in self:
            task.artwork_latest_sale_order_id = task.artwork_sale_order_id
            original_line = task.artwork_sale_order_line_id
            code = (original_line.job_code or task.name or '').strip()
            if task.artwork_sale_order_id and code:
                codes.add(code)
                companies.add(task.artwork_sale_order_id.company_id.id)

        if not codes:
            return

        # One batched lookup for all artwork tasks being computed. Do not use
        # customer as a domain: previous designs can be reused in Repeat Jobs.
        repeat_lines = self.env['sale.order.line'].search([
            ('job_code', 'in', sorted(codes)),
            ('order_id.requirement_form_id.repeat_job', '=', True),
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.company_id', 'in', sorted(companies)),
            ('display_type', '=', False),
        ])
        lines_by_code = {}
        for line in repeat_lines:
            lines_by_code.setdefault(line.job_code.strip(), []).append(line)
        for lines in lines_by_code.values():
            # Newest confirmed order wins. Use SO id as a tie breaker.
            lines.sort(
                key=lambda line: (
                    line.order_id.date_order,
                    line.order_id.id,
                ),
                reverse=True,
            )

        for task in self:
            original_order = task.artwork_sale_order_id
            original_line = task.artwork_sale_order_line_id
            if not original_order:
                continue
            code = (original_line.job_code or task.name or '').strip()
            if not code:
                continue

            for candidate in lines_by_code.get(code, []):
                order = candidate.order_id
                if order.company_id != original_order.company_id:
                    continue
                if order.id == original_order.id:
                    continue
                if task._is_matching_repeat_artwork_line(candidate):
                    task.artwork_latest_sale_order_id = order
                    break

    def _is_matching_repeat_artwork_line(self, candidate_line):
        """Check the original design chain, with GDN/legacy fallbacks."""
        self.ensure_one()
        original_line = self.artwork_sale_order_line_id
        if not original_line:
            # Older artwork tasks may have no original SO-line link.
            return True

        original_spec = original_line.requirement_specification_id
        candidate_spec = candidate_line.requirement_specification_id
        if original_spec and candidate_spec:
            visited = set()
            spec = candidate_spec
            while spec and spec.id not in visited:
                if spec == original_spec:
                    return True
                visited.add(spec.id)
                spec = spec.source_specification_id

        original_gdn = original_line.gdn_configuration_id
        if original_gdn and original_gdn == candidate_line.gdn_configuration_id:
            return True

        # Legacy records without source references: reused Job Code is the
        # remaining identifier, already scoped to the original company.
        return not original_spec and not original_gdn

    def action_open_artwork_sale_order(self):
        self.ensure_one()
        if not self.artwork_latest_sale_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.artwork_latest_sale_order_id.id,
            'target': 'current',
        }
