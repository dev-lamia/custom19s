from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleGdnDisableWizard(models.TransientModel):
    _name = 'sale.gdn.disable.wizard'
    _description = 'Disable GDN With Reason'

    gdn_ids = fields.Many2many(
        'sale.gdn.configuration',
        string='Selected GDNs',
        required=True,
        readonly=True,
    )
    reason = fields.Text(string='Reason for Disabling', required=True)

    def action_confirm_disable(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise ValidationError(_('Please provide a reason for disabling the GDN.'))
        gdns = self.gdn_ids.filtered('active')
        if not gdns:
            raise UserError(_('The selected GDN records are already disabled.'))

        # Use Odoo's normal archive convention. Existing relational links,
        # files and history are retained; the active list no longer shows them.
        gdns.write({'active': False})
        for gdn in gdns:
            gdn.message_post(
                body=Markup('<p><strong>GDN disabled.</strong> Reason: %s</p>')
                % escape(reason),
                subtype_xmlid='mail.mt_note',
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('GDN Configurations'),
            'res_model': 'sale.gdn.configuration',
            'view_mode': 'list,form',
            'target': 'current',
        }
