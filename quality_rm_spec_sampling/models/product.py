from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .master import MATERIAL_TYPES


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rm_qc_required = fields.Boolean(string='Incoming QC Required', default=False,
                                    help='An approved incoming QC specification is required before confirming a purchase order.')
    rm_qc_material_type = fields.Selection(MATERIAL_TYPES, string='RM Material Type')
    rm_qc_film_type = fields.Selection([
        ('bopp', 'BOPP'), ('pet', 'PET'), ('pe', 'PE'),
        ('cpp', 'CPP'), ('mpet', 'MPET'), ('alu', 'AL / Aluminium Foil'),
    ], string='Film Material Grade',
       help='Controls which incoming film parameters apply. AL/MPET require verified test masters.')
    rm_qc_intended_use = fields.Text(string='Intended Customer / Product / Usage')
    rm_qc_identification_line_ids = fields.One2many(
        'rm.qc.product.identification', 'product_tmpl_id',
        string='Technical Identification', domain=[('active', '=', True)])
    rm_qc_specification_ids = fields.One2many(
        'rm.qc.specification', 'product_tmpl_id', string='QC Specifications')

    rm_qc_specification_count = fields.Integer(
        string='QC Standards', compute='_compute_rm_qc_specification_count')

    @api.depends('rm_qc_specification_ids')
    def _compute_rm_qc_specification_count(self):
        # Match the smart-button list, including archived standards.
        specifications = self.env['rm.qc.specification'].with_context(
            active_test=False)
        for product in self:
            product.rm_qc_specification_count = specifications.search_count([
                ('product_tmpl_id', '=', product.id),
            ])

    def action_rm_qc_view_specifications(self):
        """Open only this product's QC standards (draft/approved/archived)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('QC Standards / TDS - %s') % self.display_name,
            'res_model': 'rm.qc.specification',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_spec_list').id,
                 'list'),
                (self.env.ref('quality_rm_spec_sampling.view_rm_qc_spec_form').id,
                 'form'),
            ],
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {
                'default_product_tmpl_id': self.id,
                'default_scope': 'incoming',
                'default_company_id': self.env.company.id,
                'active_test': False,
            },
            'target': 'current',
        }


    def _sync_rm_qc_property_lines(self):
        """Mirror the active Configuration / Product Property master on products.

        Never delete previously entered values. Non-applicable or duplicate lines
        are archived and can be restored if the Material Type changes back.
        """
        if not self:
            return
        product_types = list(set(self.mapped('rm_qc_material_type')) - {False})
        templates = self.env['rm.qc.identification.template'].search([
            ('material_type', 'in', product_types), ('active', '=', True),
        ]) if product_types else self.env['rm.qc.identification.template']
        template_map = {}
        for template in templates:
            template_map.setdefault(template.material_type, []).append(template)

        identification_model = self.env['rm.qc.product.identification'].with_context(
            active_test=False)
        existing_lines = identification_model.search([
            ('product_tmpl_id', 'in', self.ids),
        ])
        lines_by_product = {}
        for line in existing_lines:
            lines_by_product.setdefault(line.product_tmpl_id.id, []).append(line)

        for product in self:
            product_lines = lines_by_product.get(product.id, [])
            current_ids = set()
            for template in template_map.get(product.rm_qc_material_type, []):
                matches = [
                    line for line in product_lines
                    if line.template_id.id == template.id
                    or (not line.template_id and line.name == template.name)
                ]
                # Prefer existing entered data over an empty duplicate.
                matches.sort(key=lambda line: (
                    bool(line.value), bool(line.uom_text), line.active,
                ), reverse=True)
                if matches:
                    line = matches[0]
                    updates = {}
                    for key, desired in (
                        ('template_id', template.id),
                        ('name', template.name),
                        ('sequence', template.sequence),
                        ('active', True),
                    ):
                        actual = line.template_id.id if key == 'template_id' else line[key]
                        if actual != desired:
                            updates[key] = desired
                    if not line.uom_text and template.uom_text:
                        updates['uom_text'] = template.uom_text
                    if updates:
                        line.write(updates)
                else:
                    line = identification_model.create({
                        'product_tmpl_id': product.id,
                        'template_id': template.id,
                        'name': template.name,
                        'sequence': template.sequence,
                        'uom_text': template.uom_text or False,
                    })
                    product_lines.append(line)
                current_ids.add(line.id)

            stale = identification_model.browse([
                line.id for line in product_lines
                if line.id not in current_ids and line.active
            ])
            if stale:
                stale.write({'active': False})

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._sync_rm_qc_property_lines()
        return products

    def write(self, vals):
        result = super().write(vals)
        if 'rm_qc_material_type' in vals:
            self._sync_rm_qc_property_lines()
        return result

    @api.onchange('rm_qc_material_type')
    def _onchange_rm_qc_material_type_properties(self):
        """Preview the appropriate fields immediately on new unsaved products."""
        for product in self:
            # Existing products are synchronized safely on Save (no lost values).
            if product._origin.id:
                continue
            templates = self.env['rm.qc.identification.template'].search([
                ('material_type', '=', product.rm_qc_material_type),
                ('active', '=', True),
            ]) if product.rm_qc_material_type else self.env['rm.qc.identification.template']
            product.rm_qc_identification_line_ids = [
                fields.Command.create({
                    'template_id': template.id,
                    'name': template.name,
                    'sequence': template.sequence,
                    'uom_text': template.uom_text or False,
                }) for template in templates
            ]

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
