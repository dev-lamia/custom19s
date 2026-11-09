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
    job_code_ids = fields.Many2many(
        'sale.job.code.configuration',
        'artwork_wizard_job_rel', 'wizard_id', 'job_id',
        string='Job Codes',
        domain="[('id', 'in', available_job_code_ids)]",
        help='Select the Job Codes from this Sales Order to create artwork projects.',
    )
    available_job_code_ids = fields.Many2many(
        'sale.job.code.configuration',
        compute='_compute_available_job_code_ids',
        string='Available Job Codes',
    )

    @api.depends('sale_order_id')
    def _compute_available_job_code_ids(self):
        Job = self.env['sale.job.code.configuration']
        for wizard in self:
            order = wizard.sale_order_id
            if not order:
                wizard.available_job_code_ids = False
                continue
            used_line_ids = set(order.artwork_task_ids.mapped(
                'artwork_sale_order_line_id').ids)
            pending = order.order_line.filtered(
                lambda line: not line.display_type and line.job_code
                and line.id not in used_line_ids
            )
            wizard.available_job_code_ids = Job.search([
                ('order_id', '=', order.id),
                ('source_line_id', 'in', pending.ids),
                ('job_code', '!=', False),
            ]) if pending else False

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
    # @api.depends_context('uid', 'allowed_company_ids')
    # def _compute_available_template_ids(self):
    #     Project = self.env['project.project'].with_context(
    #         active_test=False
    #     )
    #     templates = Project.search([
    #         ('artwork_template_id', '=', False),
    #     ])
    #     for wizard in self:
    #         wizard.available_template_ids = templates


    def action_create_project(self):
        self.ensure_one()
        order = self.sale_order_id

        if order.state != 'sale':
            raise ValidationError(
                _('Artwork can only be created after the Sales Order is confirmed.')
            )

        if not self.project_template_id:
            raise ValidationError(_('Please select a Project Template.'))
        if not self.job_code_ids:
            raise ValidationError(_('Please select at least one Job Code.'))

        invalid_jobs = self.job_code_ids.filtered(
            lambda job: job.order_id != order or not job.source_line_id
            or not job.job_code or job.source_line_id not in order.order_line
        )
        if invalid_jobs:
            raise ValidationError(
                _('All selected Job Codes must belong to the current Sales Order.')
            )
        job_lines = self.job_code_ids.mapped('source_line_id')
        existing_lines = order.artwork_task_ids.mapped('artwork_sale_order_line_id')
        already_created = job_lines & existing_lines
        if already_created:
            raise ValidationError(
                _('Artwork already exists for these selected Job Codes: %s')
                % ', '.join(already_created.mapped('job_code'))
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
                'artwork_template_id': self.project_template_id.id,
            }

            if 'reinvoiced_sale_order_id' in Project._fields:
                project_vals['reinvoiced_sale_order_id'] = order.id
            if 'is_template' in Project._fields:
                project_vals['is_template'] = False

            project = self.project_template_id.with_context(
                copy_from_template=True,
            ).copy(default=project_vals)

            # Remove template sample tasks; create the selected job's task only.
            copied_tasks = project.task_ids
            if copied_tasks:
                copied_tasks.unlink()

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
