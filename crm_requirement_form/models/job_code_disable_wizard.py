from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleJobCodeDisableWizard(models.TransientModel):
    _name = 'sale.job.code.disable.wizard'
    _description = 'Disable Job Code With Reason'

    job_line_ids = fields.Many2many(
        'sale.order.line',
        string='Selected Job Codes',
        domain=[('job_code', '!=', False)],
        required=True,
        readonly=True,
    )
    reason = fields.Text(string='Reason for Disabling', required=True)

    def action_confirm_disable(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise ValidationError(_('Please provide a reason for disabling the Job Code.'))

        lines = self.job_line_ids.filtered(
            lambda line: line.job_code and not line.job_code_disabled
        )
        if not lines:
            raise UserError(_('The selected Job Codes are already disabled.'))

        # Only archive Job Code visibility; the Sale Order Line stays active.
        lines.with_context(skip_sale_line_linked_sync=True).write({
            'job_code_disabled': True,
        })
        jobs = self.env['sale.job.code.configuration'].with_context(
            active_test=False
        ).browse(lines.ids)
        for job in jobs:
            job.message_post(
                body=Markup('<p><strong>Job Code disabled.</strong> Reason: %s</p>')
                % escape(reason),
                subtype_xmlid='mail.mt_note',
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Code Configurations'),
            'res_model': 'sale.job.code.configuration',
            'view_mode': 'list,form',
            'target': 'current',
        }
