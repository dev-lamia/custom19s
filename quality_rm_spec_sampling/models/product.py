from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .master import MATERIAL_TYPES


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rm_qc_required = fields.Boolean(string='Incoming QC Required', default=False,
                                    help='QC specifications are required for PR/PO approval.')
    rm_qc_material_type = fields.Selection(MATERIAL_TYPES, string='RM Material Type')
    rm_qc_film_type = fields.Selection([
        ('bopp', 'BOPP'), ('pet', 'PET'), ('pe', 'PE'),
        ('cpp', 'CPP'), ('mpet', 'MPET'), ('alu', 'AL / Aluminium Foil'),
    ], string='Film Material Grade',
       help='Controls which incoming film parameters apply. AL/MPET require verified test masters.')
    rm_qc_intended_use = fields.Text(string='Intended Customer / Product / Usage')
    rm_qc_identification_line_ids = fields.One2many(
        'rm.qc.product.identification', 'product_tmpl_id', string='Technical Identification')
    rm_qc_specification_ids = fields.One2many(
        'rm.qc.specification', 'product_tmpl_id', string='QC Specifications')

    def action_rm_qc_load_identification(self):
        for product in self:
            if not product.rm_qc_material_type:
                raise UserError(_('Please set an RM Material Type first.'))
            templates = self.env['rm.qc.identification.template'].search([
                ('material_type', '=', product.rm_qc_material_type),
            ])
            existing = set(product.rm_qc_identification_line_ids.mapped('name'))
            commands = [fields.Command.create({
                'template_id': template.id,
                'name': template.name, 'sequence': template.sequence,
            }) for template in templates if template.name not in existing]
            if commands:
                product.write({'rm_qc_identification_line_ids': commands})
        return True

    def action_rm_qc_new_specification(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New RM QC Specification'),
            'res_model': 'rm.qc.specification',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_product_tmpl_id': self.id,
                'default_scope': 'incoming',
            },
        }
