from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DocumentType(models.Model):
    _name = 'tam.document.type'
    _description = 'Document Type'
    _order = 'sequence, name'

    name = fields.Char(string='Document Type', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')
    folder_ids = fields.One2many('tam.document.folder', 'type_id', string='Folders')
    folder_count = fields.Integer(string='Folder Count', compute='_compute_folder_count')

    def _compute_folder_count(self):
        for rec in self:
            rec.folder_count = self.env['tam.document.folder'].search_count([('type_id', '=', rec.id)])

    def action_view_folders(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Folders'), 'res_model': 'tam.document.folder', 'view_mode': 'list,form', 'domain': [('type_id', '=', self.id)], 'context': {'default_type_id': self.id}}


class DocumentFolder(models.Model):
    _name = 'tam.document.folder'
    _description = 'Document Folder'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'parent_path, sequence, name'

    name = fields.Char(string='Folder Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    type_id = fields.Many2one('tam.document.type', string='Document Type', required=True, index=True, ondelete='restrict')
    parent_id = fields.Many2one('tam.document.folder', string='Parent Folder', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('tam.document.folder', 'parent_id', string='Subfolders')
    file_ids = fields.One2many('tam.document.file', 'folder_id', string='Files')
    complete_name = fields.Char(string='Full Path', compute='_compute_complete_name', recursive=True)
    file_count = fields.Integer(string='File Count', compute='_compute_file_count')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = '%s / %s' % (rec.parent_id.complete_name, rec.name) if rec.parent_id else rec.name

    def _compute_file_count(self):
        for rec in self:
            rec.file_count = self.env['tam.document.file'].search_count([('folder_id', '=', rec.id)])

    @api.constrains('parent_id', 'type_id')
    def _check_parent(self):
        for rec in self:
            if rec.parent_id:
                if rec.parent_id.type_id != rec.type_id:
                    raise ValidationError(_('Parent folder must have the same Document Type.'))
                if rec.parent_id == rec or rec.id in rec.parent_id.search([('id', 'child_of', rec.id)]).ids:
                    raise ValidationError(_('A folder cannot be its own parent or descendant.'))

    def action_view_files(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Files'), 'res_model': 'tam.document.file', 'view_mode': 'list,form', 'domain': [('folder_id', '=', self.id)], 'context': {'default_folder_id': self.id, 'default_type_id': self.type_id.id}}


class DocumentFile(models.Model):
    _name = 'tam.document.file'
    _description = 'Document File'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Description', required=True, tracking=True)
    type_id = fields.Many2one('tam.document.type', string='Document Type', required=True, index=True, ondelete='restrict', tracking=True)
    folder_id = fields.Many2one('tam.document.folder', string='Folder', required=True, index=True, ondelete='restrict', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', 'tam_document_file_attachment_rel', 'document_id', 'attachment_id', string='Files', help='Attach multiple files to this document.')
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    notes = fields.Text(string='Notes')

    @api.onchange('type_id')
    def _onchange_type_id(self):
        if self.folder_id and self.folder_id.type_id != self.type_id:
            self.folder_id = False

    @api.constrains('type_id', 'folder_id')
    def _check_folder_type(self):
        for rec in self:
            if rec.folder_id and rec.folder_id.type_id != rec.type_id:
                raise ValidationError(_('Folder must belong to the selected Document Type.'))
