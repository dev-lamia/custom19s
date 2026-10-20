from lxml import etree

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProfessionalApprovalButton(models.Model):
    _name = 'professional.approval.button'
    _description = 'Approval Button'
    _order = 'model_id, button_label, method_name'
    _rec_name = 'display_name'

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        index=True,
    )
    model_name = fields.Char(
        string='Model Technical Name',
        related='model_id.model',
        store=True,
        readonly=True,
        index=True,
    )
    method_name = fields.Char(string='Method Name', required=True, index=True)
    button_label = fields.Char(string='Button Label', required=True)
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    _sql_constraints = [
        (
            'model_method_unique',
            'unique(model_id, method_name)',
            'This button method is already registered for the selected model.',
        ),
    ]

    @api.depends('button_label', 'method_name', 'model_id.name')
    def _compute_display_name(self):
        for rec in self:
            label = rec.button_label or rec.method_name or ''
            model = rec.model_id.name or rec.model_name or ''
            rec.display_name = '%s (%s)' % (label, model) if model else label

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Ensure the selected model is scanned before opening the dropdown."""
        domain = list(domain or [])
        model_ids = set()

        context_model_id = self.env.context.get('approval_model_id')
        if isinstance(context_model_id, int):
            model_ids.add(context_model_id)
        elif isinstance(context_model_id, str) and context_model_id.isdigit():
            model_ids.add(int(context_model_id))

        for term in domain:
            if not isinstance(term, (list, tuple)) or len(term) != 3:
                continue
            field_name, term_operator, value = term
            if field_name != 'model_id':
                continue
            if term_operator == '=':
                if isinstance(value, int):
                    model_ids.add(value)
                elif isinstance(value, str) and value.isdigit():
                    model_ids.add(int(value))
            elif term_operator == 'in' and isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, int):
                        model_ids.add(item)
                    elif isinstance(item, str) and item.isdigit():
                        model_ids.add(int(item))

        if not self.env.context.get('skip_dynamic_button_refresh'):
            for model_id in model_ids:
                self.sudo().with_context(
                    skip_dynamic_button_refresh=True,
                ).refresh_model_buttons(model_id)

        return super().name_search(
            name=name,
            domain=domain,
            operator=operator,
            limit=limit,
        )

    @api.model
    def refresh_model_buttons(self, model_id):
        """Refresh protectable object buttons for one model.

        Scan both the raw architecture of every form extension and the fully
        combined architecture of primary form views. Some applications (for
        example Payroll) add their buttons only through inherited views, so
        scanning combined arches alone can silently return no buttons.
        """
        service = self.sudo().with_context(skip_dynamic_button_refresh=True)
        model = service.env['ir.model'].browse(model_id)
        if not model.exists() or not model.model:
            return self.browse()

        buttons = {}
        view_model = service.env['ir.ui.view'].with_context(active_test=False)
        views = view_model.search([
            ('type', '=', 'form'),
            '|',
            ('model', '=', model.model),
            ('inherit_id.model', '=', model.model),
        ])

        def _parse_arch(arch, view):
            if not arch:
                return
            try:
                if isinstance(arch, etree._Element):
                    root = arch
                elif isinstance(arch, bytes):
                    root = etree.fromstring(arch)
                else:
                    root = etree.fromstring(str(arch).encode('utf-8'))
            except Exception as exc:
                _logger.debug(
                    'Approval button XML parse skipped view %s for model %s: %s',
                    view.id, model.model, exc,
                )
                return

            for node in root.xpath(".//button[@type='object'][@name]"):
                method = (node.get('name') or '').strip()
                if not method or method.startswith('_'):
                    continue
                if node.get('invisible') == '1' and not node.get('string'):
                    continue
                label = node.get('string') or method.replace('_', ' ').title()
                buttons.setdefault(method, label)

        # Raw arches are essential for extension views whose buttons may not
        # be present when another extension is used as the combination root.
        for view in views:
            _parse_arch(view.arch_db, view)

        # Combined arches resolve xpath additions and translated final labels.
        primary_views = views.filtered(lambda view: view.mode == 'primary' or not view.inherit_id)
        for view in primary_views:
            try:
                _parse_arch(view._get_combined_arch(), view)
            except Exception as exc:
                _logger.debug(
                    'Approval combined view scan skipped view %s for model %s: %s',
                    view.id, model.model, exc,
                )

        # Fallback for models whose form buttons are injected at runtime or
        # whose payroll views are supplied by optional enterprise modules. In
        # those cases ir.ui.view may not expose the final button architecture
        # while this onchange runs. Only collect explicit business-action
        # methods; framework/private methods remain excluded.
        try:
            model_recordset = service.env[model.model]
        except KeyError:
            model_recordset = False

        if model_recordset:
            business_method_names = {'unlink'}
            excluded_names = {
                'action_archive',
                'action_unarchive',
                'action_duplicate',
            }
            for method_name in dir(model_recordset):
                if method_name in excluded_names or method_name.startswith('_'):
                    continue
                if method_name.startswith(('action_', 'button_')):
                    business_method_names.add(method_name)

            for method_name in sorted(business_method_names):
                if method_name.startswith('_'):
                    continue
                method = getattr(model_recordset, method_name, None)
                if not callable(method):
                    continue
                label = method_name
                if method_name == 'unlink':
                    label = _('Delete')
                else:
                    label = method_name.removeprefix('action_')
                    label = label.removeprefix('button_')
                    label = label.replace('_', ' ').title()
                buttons.setdefault(method_name, label)

        records = self.browse()
        for method, label in buttons.items():
            record = service.search([
                ('model_id', '=', model.id),
                ('method_name', '=', method),
            ], limit=1)
            vals = {'button_label': label}
            if record:
                record.write(vals)
            else:
                vals.update({'model_id': model.id, 'method_name': method})
                record = service.create(vals)
            records |= record
        return records
