from odoo import api, fields, models


class RequirementDocumentType(models.Model):
    """Document categories maintained from Requirement Configuration."""

    _name = 'crm.requirement.document.type'
    _description = 'Requirement Document Type'
    _order = 'sequence, name, id'

    name = fields.Char(string='Document Type', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    @api.model
    def _get_or_create_by_name(self, name):
        """Resolve legacy free-text types without dropping their documents."""
        name = (name or '').strip()
        if not name:
            return self.browse()
        existing = self.with_context(active_test=False).search([
            ('name', '=ilike', name),
        ], limit=1)
        if existing:
            return existing
        return self.sudo().create({'name': name})

    @api.model
    def _backfill_document_type_ids(self):
        """One-time/idempotent link of existing text types to config entries."""
        for model_name in (
            'crm.requirement.design.document.line',
            'sale.gdn.document.line',
        ):
            records = self.env[model_name].sudo().search([
                ('document_type_id', '=', False),
            ])
            for record in records:
                if record.document_type:
                    option = self._get_or_create_by_name(record.document_type)
                    if option:
                        record.with_context(skip_document_type_sync=True).write({
                            'document_type_id': option.id,
                        })
        return True

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals:
            # Existing synchronization still expects the text label.
            for option in self:
                for model_name in (
                    'crm.requirement.design.document.line',
                    'sale.gdn.document.line',
                ):
                    self.env[model_name].sudo().search([
                        ('document_type_id', '=', option.id),
                    ]).with_context(skip_document_type_sync=True).write({
                        'document_type': option.name,
                    })
        return result
