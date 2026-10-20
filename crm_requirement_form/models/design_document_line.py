from odoo import api, fields, models


class RequirementDesignDocumentLine(models.Model):
    """One document category and its multiple files for a single design."""

    _name = 'crm.requirement.design.document.line'
    _description = 'Requirement Design Document Line'
    _rec_name = 'document_type'
    _order = 'sequence, id'

    specification_id = fields.Many2one(
        'crm.requirement.specification',
        string='Product Specification',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    document_type = fields.Char(string='Document Type', required=True)
    document_type_id = fields.Many2one(
        'crm.requirement.document.type',
        string='Document Type',
        ondelete='restrict',
        index=True,
    )

    @api.onchange('document_type_id')
    def _onchange_document_type_id(self):
        for line in self:
            if line.document_type_id:
                line.document_type = line.document_type_id.name

    def _normalize_document_types(self, vals_list):
        options = self.env['crm.requirement.document.type']
        for values in vals_list:
            option_id = values.get('document_type_id')
            if option_id:
                values['document_type'] = options.browse(option_id).name
            elif values.get('document_type'):
                option = options._get_or_create_by_name(values['document_type'])
                values['document_type_id'] = option.id
        return vals_list

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'crm_req_design_doc_line_attachment_rel',
        'document_line_id',
        'attachment_id',
        string='Documents',
        copy=True,
        help='Upload one or more files for this document type.',
    )

    def _sync_linked_gdn_documents(self, specifications=None):
        specifications = specifications or self.mapped('specification_id')
        if specifications:
            gdns = specifications.mapped('sale_order_line_ids.gdn_configuration_id')
            if gdns:
                gdns.sudo()._sync_document_lines()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._normalize_document_types(vals_list)
        records = super().create(vals_list)
        records._sync_linked_gdn_documents()
        return records

    def write(self, vals):
        old_specifications = self.mapped('specification_id')
        if not self.env.context.get('skip_document_type_sync'):
            vals = dict(vals)
            if vals.get('document_type_id'):
                vals['document_type'] = self.env[
                    'crm.requirement.document.type'
                ].browse(vals['document_type_id']).name
            elif vals.get('document_type'):
                option = (
                    self.env['crm.requirement.document.type']
                    ._get_or_create_by_name(vals['document_type'])
                )
                vals['document_type_id'] = option.id
        result = super().write(vals)
        if {'document_type', 'attachment_ids', 'specification_id', 'sequence'} & set(vals):
            self._sync_linked_gdn_documents(old_specifications | self.mapped('specification_id'))
        return result

    def unlink(self):
        specifications = self.mapped('specification_id')
        # Preserve manually uploaded GDN files if a source document row is removed.
        linked_rows = self.env['sale.gdn.document.line'].sudo().search([
            ('source_design_document_line_id', 'in', self.ids),
        ])
        for row in linked_rows:
            own_ids = set(row.attachment_ids.ids) - set(row.source_attachment_ids.ids)
            if own_ids:
                row.write({
                    'source_design_document_line_id': False,
                    'source_attachment_ids': [(5, 0, 0)],
                    'attachment_ids': [(6, 0, sorted(own_ids))],
                })
            else:
                row.unlink()
        result = super().unlink()
        self._sync_linked_gdn_documents(specifications)
        return result
