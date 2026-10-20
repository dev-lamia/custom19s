from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleJobCodeDocumentLine(models.Model):
    """Job Code document rows backed by their original design documents.

    Job Code is a SQL view, so the real owner is the Sale Order Line.  The
    related fields deliberately reuse the specification documents and uploads
    instead of making detached copies of attachments.
    """

    _name = 'sale.job.code.document.line'
    _description = 'Job Code Document Line'
    _order = 'sequence, id'
    _rec_name = 'document_type'

    source_line_id = fields.Many2one(
        'sale.order.line',
        string='Job Code Sale Order Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    source_design_document_line_id = fields.Many2one(
        'crm.requirement.design.document.line',
        string='Source Design Document',
        required=True,
        ondelete='cascade',
        index=True,
        copy=False,
    )
    sequence = fields.Integer(
        related='source_design_document_line_id.sequence',
        string='Sequence',
        readonly=False,
        store=True,  # Needed by _order and the draggable handle in Odoo lists.
    )
    document_type = fields.Char(
        related='source_design_document_line_id.document_type',
        string='Document Type',
        readonly=False,
    )
    document_type_id = fields.Many2one(
        'crm.requirement.document.type',
        related='source_design_document_line_id.document_type_id',
        string='Document Type',
        readonly=False,
        domain=[],
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        related='source_design_document_line_id.attachment_ids',
        string='Documents',
        readonly=False,
    )

    _unique_sale_line_design_document = models.Constraint(
        'UNIQUE(source_line_id, source_design_document_line_id)',
        'A Job Code cannot link the same design document twice.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            source_line = self.env['sale.order.line'].browse(
                vals.get('source_line_id')
            ).exists()
            if not source_line or not source_line.requirement_specification_id:
                raise UserError(
                    'A linked Product Specification is required to add Job Code documents.'
                )
            if not vals.get('source_design_document_line_id'):
                if source_line.requirement_specification_id.is_duplicate_copy:
                    raise UserError(
                        'Documents on a duplicate specification are read-only.'
                    )
                source_values = {
                    'specification_id': source_line.requirement_specification_id.id,
                }
                for name in (
                    'sequence', 'document_type', 'document_type_id',
                    'attachment_ids',
                ):
                    if name in vals:
                        source_values[name] = vals.pop(name)
                # Job Code's row and its backing document are created together.
                # Prevent the source create hook from also adding a second row.
                design_doc = self.env[
                    'crm.requirement.design.document.line'
                ].with_context(skip_job_code_document_bootstrap=True).create(
                    source_values
                )
                vals['source_design_document_line_id'] = design_doc.id
            prepared.append(vals)
        records = super().create(prepared)
        if not self.env.context.get('skip_job_code_document_bootstrap'):
            records.mapped(
                'source_design_document_line_id.specification_id.sale_order_line_ids'
            )._sync_job_code_document_rows()
        return records

    def unlink(self):
        documents = self.mapped('source_design_document_line_id')
        result = super().unlink()
        # Backfill/relationship cleanup must not delete the shared source.
        if not self.env.context.get('keep_source_design_document') and documents:
            documents.unlink()
        return result
