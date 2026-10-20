from odoo import api, fields, models


class SaleGdnDocumentLine(models.Model):
    """Editable GDN document categories and their multiple uploaded files."""

    _name = 'sale.gdn.document.line'
    _description = 'GDN Document Line'
    _order = 'sequence, id'
    _rec_name = 'document_type'

    gdn_configuration_id = fields.Many2one(
        'sale.gdn.configuration',
        string='GDN Configuration',
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
        'sale_gdn_document_line_attachment_rel',
        'gdn_document_line_id',
        'attachment_id',
        string='Documents',
        copy=False,
        help='Attach one or more files to this GDN document type.',
    )
    # Internal provenance keeps REQ file changes in sync without deleting
    # independently uploaded GDN attachments.
    source_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sale_gdn_document_line_source_attachment_rel',
        'gdn_document_line_id',
        'attachment_id',
        string='Source Design Files',
        copy=False,
        readonly=True,
    )
    source_design_document_line_id = fields.Many2one(
        'crm.requirement.design.document.line',
        string='Source Design Document Line',
        ondelete='set null',
        readonly=True,
        index=True,
        help='Set when this row originally came from the Requirement Form design.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(self._normalize_document_types(vals_list))

    def write(self, vals):
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
        return super().write(vals)
