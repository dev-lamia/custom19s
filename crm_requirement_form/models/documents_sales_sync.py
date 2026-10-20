"""Mirror Requirement Form uploads into Finance / Sales / Requirement Form.

Keep the original ir.attachment untouched: Documents gets its own copy, so
its inverse attachment logic cannot move a file away from the Requirement Form.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class CrmRequirementFormSalesDocuments(models.Model):
    _inherit = 'crm.requirement.form'

    def _sales_documents_folder(self):
        """Find Company / Finance / Sales / Requirement Form workspace."""
        if 'documents.document' not in self.env.registry:
            return False
        Document = self.env['documents.document'].sudo()
        candidates = Document.search([
            ('name', '=', 'Requirement Form'),
            ('type', '=', 'folder'),
            ('company_id', 'in', [False, self.env.company.id]),
        ])
        for candidate in candidates:
            sales = candidate.folder_id
            finance = sales.folder_id if sales else False
            if (sales and sales.name == 'Sales'
                    and finance and finance.name == 'Finance'):
                return candidate
        _logger.warning(
            'Requirement Sales Documents: Company / Finance / Sales / '
            'Requirement Form workspace not found for company %s',
            self.env.company.display_name,
        )
        return False

    def _sync_sales_documents(self):
        folder = self._sales_documents_folder()
        if not folder:
            return
        Document = self.env['documents.document'].sudo()
        attachments = self.mapped('document_attachment_ids')
        attachments |= self.mapped('partner_id.requirement_document_attachment_ids')
        for attachment in attachments.sudo():
            # Track the copy using an external ID, avoiding an extra SQL column
            # on ir.attachment (which would crash until a module upgrade).
            mapping_name = 'sales_document_attachment_%s' % attachment.id
            mapping = self.env['ir.model.data'].sudo().search([
                ('module', '=', 'crm_requirement_form'),
                ('name', '=', mapping_name),
                ('model', '=', 'documents.document'),
            ], limit=1)
            if mapping:
                mapped_document = Document.browse(mapping.res_id).exists()
                if mapped_document:
                    if mapped_document.folder_id != folder:
                        mapped_document.write({'folder_id': folder.id})
                    continue
            if mapping:
                mapping.unlink()
            # Reuse an already-linked Documents entry if another app created one.
            existing = Document.search([('attachment_id', '=', attachment.id)], limit=1)
            if existing:
                if existing.folder_id != folder:
                    existing.write({'folder_id': folder.id})
                document = existing
            else:
                # Copying prevents Documents from relocating the source attachment.
                copy_attachment = attachment.copy({
                    'res_model': False, 'res_id': 0, 'res_field': False,
                })
                document = Document.create({
                    'name': attachment.name,
                    'type': 'binary',
                    'folder_id': folder.id,
                    'attachment_id': copy_attachment.id,
                })
            self.env['ir.model.data'].sudo().create({
                'module': 'crm_requirement_form',
                'name': mapping_name,
                'model': 'documents.document',
                'res_id': document.id,
                'noupdate': True,
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_sales_documents()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'document_attachment_ids' in vals or 'partner_id' in vals:
            self._sync_sales_documents()
        return result

    @api.model
    def _cron_sync_existing_sales_documents(self):
        if not self._sales_documents_folder():
            return
        # Include files uploaded before this integration was installed.
        forms = self.sudo().search([], order='id')
        forms._sync_sales_documents()
        _logger.info('Requirement Sales Documents: processed %s forms', len(forms))

class ResPartnerRequirementSalesDocuments(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        result = super().write(vals)
        if 'requirement_document_attachment_ids' in vals:
            forms = self.env['crm.requirement.form'].sudo().search([
                ('partner_id', 'in', self.ids),
            ])
            forms._sync_sales_documents()
        return result
