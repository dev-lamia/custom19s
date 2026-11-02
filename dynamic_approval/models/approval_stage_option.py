from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProfessionalApprovalStageOption(models.Model):
    """Stage/status choices discovered from the selected business model.

    Supports native selection fields and stage-like Many2one fields, without
    adding fixed dependencies on CRM, sales, projects, or custom modules.
    """

    _name = 'professional.approval.stage.option'
    _description = 'Dynamic Approval Stage or Status Option'
    _order = 'field_id, name, id'

    field_id = fields.Many2one(
        'ir.model.fields', string='Stage / Status Field', required=True,
        ondelete='cascade', index=True,
    )
    name = fields.Char(string='Stage / Status', required=True)
    value = fields.Char(string='Technical Value', required=True, index=True)

    @api.constrains('field_id', 'value')
    def _check_unique_option(self):
        # Do not permit ambiguous options, including when records are imported.
        for option in self:
            if self.search_count([
                ('id', '!=', option.id),
                ('field_id', '=', option.field_id.id),
                ('value', '=', option.value),
            ]):
                raise ValidationError(_('This stage/status value already exists.'))

    @api.model
    def refresh_for_field(self, field_id):
        """Synchronize selectable values without deleting referenced entries."""
        if not field_id:
            return self.browse()
        field = self.env['ir.model.fields'].sudo().browse(int(field_id)).exists()
        if not field or field.ttype not in ('selection', 'many2one'):
            return self.browse()

        try:
            source = self.env[field.model]
        except KeyError:
            return self.browse()
        if field.name not in source._fields:
            return self.browse()

        choices = []
        if field.ttype == 'selection':
            description = source.sudo().fields_get(
                [field.name], attributes=['selection']
            ).get(field.name, {})
            for value, label in description.get('selection') or []:
                if value is not False and value is not None and str(value):
                    choices.append((str(value), str(label)))
        else:
            relation = source._fields[field.name].comodel_name
            if not relation:
                return self.browse()
            try:
                stage_model = self.env[relation]
            except KeyError:
                return self.browse()
            # Stage models generally contain a small number of records.
            # Cap discovery so selecting a poorly named relation cannot cause
            # an unbounded table read during an onchange/name_search.
            stages = stage_model.sudo().search([], limit=500)
            choices = [(str(stage.id), stage.display_name) for stage in stages]

        options = self.sudo()
        current = options.search([('field_id', '=', field.id)])
        by_value = {row.value: row for row in current}
        for value, label in choices:
            existing = by_value.get(value)
            if existing:
                if existing.name != label:
                    existing.write({'name': label})
            else:
                options.create({
                    'field_id': field.id, 'name': label, 'value': value,
                })
        return options.search([('field_id', '=', field.id)])

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        field_id = self.env.context.get('approval_stage_field_id')
        if isinstance(field_id, (int, str)) and str(field_id).isdigit():
            self.sudo().refresh_for_field(int(field_id))
        return super().name_search(
            name=name, domain=domain, operator=operator, limit=limit,
        )
