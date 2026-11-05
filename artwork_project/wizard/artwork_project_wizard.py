from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArtworkProjectCreateWizard(models.TransientModel):
    _name = 'artwork.project.create.wizard'
    _description = 'Create Artwork Projects'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        readonly=True,
    )
    project_template_id = fields.Many2one(
        'project.project',
        string='Project Template',
        domain="[('id', 'in', available_template_ids)]",
        help='Select a project template whose project configuration and stages should be used for each artwork project.',
    )
    available_template_ids = fields.Many2many(
        'project.project',
        compute='_compute_available_template_ids',
    )

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_available_template_ids(self):
        Project = self.env['project.project']
        domain = []
        if 'is_template' in Project._fields:
            domain.append(('is_template', '=', True))
        if 'active' in Project._fields:
            domain.append(('active', '=', True))
        templates = Project.search(domain)
        for wizard in self:
            wizard.available_template_ids = templates

    def action_create_project(self):
        self.ensure_one()
        order = self.sale_order_id

        if order.state != 'sale':
            raise ValidationError(
                _('Artwork can only be created after the Sales Order is confirmed.')
            )

        job_lines = order.order_line.filtered(
            lambda line: not line.display_type and line.job_code
        )
        if not job_lines:
            raise ValidationError(
                _('No Sales Order line with a Job Code was found.')
            )

        if order.artwork_task_ids:
            raise ValidationError(
                _('Artwork has already been created for this Sales Order.')
            )

        Project = self.env['project.project']
        Task = self.env['project.task']
        created_projects = self.env['project.project']

        for line in job_lines:
            job_code = line.job_code.strip() if isinstance(line.job_code, str) else line.job_code
            if not job_code:
                continue

            project_vals = {
                'name': job_code,
                'partner_id': order.partner_id.id,
                'company_id': order.company_id.id,
                'artwork_sale_order_id': order.id,
            }

            if 'reinvoiced_sale_order_id' in Project._fields:
                project_vals['reinvoiced_sale_order_id'] = order.id
            if 'is_template' in Project._fields:
                project_vals['is_template'] = False

            if self.project_template_id:
                project = self.project_template_id.with_context(
                    copy_from_template=True,
                ).copy(default=project_vals)

                # A template can contain example tasks. Artwork projects must
                # contain exactly one task, so remove copied template tasks.
                copied_tasks = project.task_ids
                if copied_tasks:
                    copied_tasks.unlink()
            else:
                project = Project.create(project_vals)

            Task.create({
                'name': job_code,
                'project_id': project.id,
                'partner_id': order.partner_id.id,
                'artwork_sale_order_id': order.id,
                'artwork_sale_order_line_id': line.id,
            })

            created_projects |= project

        if not created_projects:
            raise ValidationError(
                _('No valid Job Code was found on the Sales Order lines.')
            )

        if len(created_projects) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Artwork Project'),
                'res_model': 'project.project',
                'view_mode': 'form',
                'res_id': created_projects.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Artwork Projects'),
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_projects.ids)],
            'context': {'create': False},
            'target': 'current',
        }
