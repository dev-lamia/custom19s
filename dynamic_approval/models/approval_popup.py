from odoo import fields, models


class ProfessionalApprovalPopup(models.TransientModel):
    _name = 'professional.approval.popup'
    _description = 'Approval Message'

    message = fields.Text(string='Message', readonly=True)
