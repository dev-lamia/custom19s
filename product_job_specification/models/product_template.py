from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    spec_job_id = fields.Many2one(
        'sale.job.code.configuration', string='Job Code', index=True,
        ondelete='set null',
        help='Choose the Job Code whose production data should be displayed.',
    )
    spec_design_name = fields.Char(string='Design Name', compute='_compute_job_spec')
    spec_customer_id = fields.Many2one(
        'res.partner', string='Customer Name', compute='_compute_job_spec',
    )
    spec_customer_code = fields.Char(string='Customer Code', compute='_compute_job_spec')
    spec_one_up_size = fields.Char(string='One Up Size', compute='_compute_job_spec')
    spec_num_ups = fields.Integer(string='No. of Ups', compute='_compute_job_spec')
    spec_one_repeat_size = fields.Float(
        string='One Repeat Size', compute='_compute_job_spec', digits=(16, 2),
    )
    spec_num_repeats = fields.Integer(
        string='No. of Repeats', compute='_compute_job_spec',
    )
    spec_circumference = fields.Float(
        string='Circumference', compute='_compute_job_spec', digits=(16, 2),
    )
    spec_print_width = fields.Float(
        string='Print Width', compute='_compute_job_spec', digits=(16, 2),
    )
    spec_film_width = fields.Char(string='Film Width', compute='_compute_job_spec')
    spec_sleeve_size = fields.Char(string='Sleeve Size', compute='_compute_job_spec')

    @api.depends('spec_job_id')
    def _compute_job_spec(self):
        for rec in self:
            job = rec.spec_job_id
            rec.spec_design_name = job.design_name or False if job else False
            rec.spec_customer_id = job.partner_id if job else False
            rec.spec_customer_code = (
                job.partner_id.customer_code or False if job else False
            )
            rec.spec_one_up_size = job.job_one_up_size or False if job else False
            rec.spec_num_ups = job.job_number_of_ups or 0 if job else 0
            # This optional field exists in some deployed Job Code versions.
            rec.spec_one_repeat_size = (
                job.job_one_repeat_size or 0.0
                if job and 'job_one_repeat_size' in job._fields else 0.0
            )
            rec.spec_num_repeats = job.job_number_of_repeats or 0 if job else 0
            rec.spec_circumference = job.job_circumference or 0.0 if job else 0.0
            rec.spec_print_width = job.job_print_area or 0.0 if job else 0.0
            rec.spec_film_width = (
                job.job_film_size_to_be_used or False if job else False
            )
            rec.spec_sleeve_size = job.job_sleeve_size or False if job else False
