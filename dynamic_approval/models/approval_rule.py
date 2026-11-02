import ast
import logging
from functools import wraps

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class ProfessionalApprovalRuleApprover(models.Model):
    _name = 'professional.approval.rule.approver'
    _description = 'Approval Rule Approver'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'professional.approval.rule',
        string='Rule',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Approver', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    required = fields.Boolean(string='Required', default=True)


class ProfessionalApprovalStageApprover(models.Model):
    """One configured approver for one selectable stage/status."""

    _name = 'professional.approval.stage.approver'
    _description = 'Stage / Status Approver Assignment'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'professional.approval.rule', string='Approval Rule',
        required=True, ondelete='cascade', index=True,
    )
    stage_field_id = fields.Many2one(
        'ir.model.fields', string='Stage Field',
        related='rule_id.stage_field_id', readonly=True,
    )
    stage_option_id = fields.Many2one(
        'professional.approval.stage.option', string='Stage / Status',
        required=True, ondelete='restrict', index=True,
        domain="[('field_id', '=', stage_field_id)]",
    )
    user_id = fields.Many2one(
        'res.users', string='Approver',
        help='Leave empty to skip approval for this stage.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    required = fields.Boolean(string='Required', default=True)

    @api.constrains('rule_id', 'stage_option_id', 'user_id')
    def _check_assignment(self):
        for line in self:
            if (line.stage_option_id and line.rule_id.stage_field_id
                    and line.stage_option_id.field_id != line.rule_id.stage_field_id):
                raise ValidationError(_(
                    'The selected stage does not belong to this rule stage field.'
                ))
            if line.user_id and self.search_count([
                ('id', '!=', line.id), ('rule_id', '=', line.rule_id.id),
                ('stage_option_id', '=', line.stage_option_id.id),
                ('user_id', '=', line.user_id.id),
            ]):
                raise ValidationError(_(
                    'This approver is already configured for the same stage.'
                ))


class ProfessionalApprovalRule(models.Model):
    _name = 'professional.approval.rule'
    _description = 'Dynamic Approval Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Rule Name', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    sequence = fields.Integer(string='Priority', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Legacy Company',
        index=True,
        help='Compatibility field for rules created by earlier module versions.',
    )
    company_ids = fields.Many2many(
        'res.company',
        'professional_approval_rule_company_rel',
        'rule_id',
        'company_id',
        string='Applicable Companies',
        help=(
            'Leave empty to apply this rule to every company. Select one or '
            'more companies to limit the rule to those companies.'
        ),
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    model_name = fields.Char(
        string='Model Technical Name',
        related='model_id.model',
        store=True,
        readonly=True,
        index=True,
    )
    button_id = fields.Many2one(
        'professional.approval.button',
        string='Button / Action',
        required=False,
        domain="[('model_id', '=', model_id)]",
        tracking=True,
    )
    method_name = fields.Char(
        string='Technical Method',
        related='button_id.method_name',
        store=True,
        readonly=True,
        index=True,
    )
    stage_field_id = fields.Many2one(
        'ir.model.fields',
        string='Stage / Status Field',
        ondelete='set null',
        help=(
            'Optional: select a stage/status field of the business model. '
            'The approval rule applies only while the document is in the '
            'chosen stage/status.'
        ),
    )
    stage_option_id = fields.Many2one(
        'professional.approval.stage.option',
        string='Stage / Status Value',
        ondelete='restrict',
        domain="[('field_id', '=', stage_field_id)]",
        help='Select the current value that should require these approvers.',
    )
    use_stage_approvers = fields.Boolean(
        string='Set Approvers by Stage / Status',
        default=False,
        tracking=True,
        help=(
            'When enabled, select the approver separately for every stage. '
            'Only stages with an assigned user require approval for the selected button.'
        ),
    )
    stage_approver_line_ids = fields.One2many(
        'professional.approval.stage.approver', 'rule_id',
        string='Stage / Status Approvers', copy=True,
    )
    initiator_ids = fields.Many2many(
        'res.users',
        'professional_approval_rule_initiator_rel',
        'rule_id',
        'user_id',
        string='Allowed Initiators',
        help='Leave empty to allow every internal user to start this approval.',
    )
    approver_line_ids = fields.One2many(
        'professional.approval.rule.approver',
        'rule_id',
        string='Approvers',
        copy=True,
    )
    sequential_approval = fields.Boolean(
        string='Approve by Sequence',
        default=True,
        tracking=True,
    )
    minimum_approvals = fields.Integer(
        string='Minimum Approvals',
        default=1,
        help='Required approvers must always approve. This value controls the minimum total approved lines.',
    )
    condition_domain = fields.Text(
        string='Condition Domain',
        default='[]',
        help='Optional domain applied on the source record. Example: [("amount_total", ">", 50000)]',
    )
    request_count = fields.Integer(
        string='Requests',
        compute='_compute_request_count',
    )


    def _register_hook(self):
        """Restore approval wrappers whenever the Odoo registry starts.

        Dynamic Python wrappers are process-local. Saving a rule installs the
        wrapper only in the current worker, so a restart or another worker can
        otherwise execute the protected button without approval.
        """
        result = super()._register_hook()
        try:
            with self.env.cr.savepoint():
                rules = self.sudo().search([
                    ('active', '=', True),
                    ('model_name', '!=', False),
                ])
                for rule in rules:
                    rule._install_state_write_wrapper(rule.model_name)
                    if rule.method_name:
                        rule._install_method_wrapper(
                            rule.model_name,
                            rule.method_name,
                        )
        except Exception:
            # During the first installation the model table may not exist yet.
            # create() installs wrappers after the XML records are loaded.
            _logger.debug(
                'Approval wrappers will be installed after data loading.',
                exc_info=True,
            )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._install_related_wrappers()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'active', 'model_id', 'button_id', 'use_stage_approvers', 'stage_field_id'} & set(vals):
            self._install_related_wrappers()
        return res

    def _install_related_wrappers(self):
        """Install Python method wrappers immediately after rule changes.

        Views can be cached in the browser/server. If we only patch while loading
        a form view, a button that was already opened before creating the rule can
        still execute normally. Installing here makes the approval check active
        as soon as the rule is saved/upgraded.
        """
        for rec in self.sudo().filtered(
            lambda rule: rule.active and rule.model_name and (rule.method_name or rule.use_stage_approvers)
        ):
            rec._install_state_write_wrapper(rec.model_name)
            rec._install_method_wrapper(rec.model_name, rec.method_name)
        return True

    @api.depends('model_id')
    def _compute_request_count(self):
        request_model = self.env.registry.get('professional.approval.request')
        request_table = getattr(request_model, '_table', False) if request_model else False
        table_ready = False
        if request_table:
            with self.env.cr.savepoint():
                self.env.cr.execute('SELECT to_regclass(%s)', (request_table,))
                table_ready = bool(self.env.cr.fetchone()[0])
        if not table_ready:
            for rec in self:
                rec.request_count = 0
            return
        grouped = self.env['professional.approval.request'].read_group(
            [('rule_id', 'in', self.ids)],
            ['rule_id'],
            ['rule_id'],
        )
        count_by_rule = {row['rule_id'][0]: row['rule_id_count'] for row in grouped}
        for rec in self:
            rec.request_count = count_by_rule.get(rec.id, 0)

    @api.constrains(
        'approver_line_ids', 'stage_approver_line_ids',
        'minimum_approvals', 'use_stage_approvers',
    )
    def _check_approvers(self):
        for rec in self:
            if rec.minimum_approvals < 1:
                raise ValidationError(_('Minimum approvals must be at least 1.'))
            if rec.use_stage_approvers:
                mapped_lines = rec.stage_approver_line_ids.filtered('user_id')
                if not mapped_lines:
                    raise ValidationError(_(
                        'Assign an approver to at least one Stage / Status row.'
                    ))
                # Different stages may have different approver counts; the
                # request caps its threshold to the selected stage's count.
            else:
                if not rec.approver_line_ids:
                    raise ValidationError(_('Please add at least one approver.'))
                if rec.minimum_approvals > len(rec.approver_line_ids):
                    raise ValidationError(_(
                        'Minimum approvals cannot exceed approver count.'
                    ))

    @api.constrains(
        'model_id', 'stage_field_id', 'stage_option_id',
        'use_stage_approvers', 'stage_approver_line_ids',
    )
    def _check_stage_configuration(self):
        for rec in self:
            if rec.use_stage_approvers:
                if not rec.stage_field_id:
                    raise ValidationError(_(
                        'Select the Stage / Status Field for stage-wise approvers.'
                    ))
                if rec.stage_option_id:
                    raise ValidationError(_(
                        'Clear the single Stage / Status Value when using stage-wise approvers.'
                    ))
            elif not rec.stage_field_id and not rec.stage_option_id:
                continue
            elif not rec.stage_field_id or not rec.stage_option_id:
                raise ValidationError(_(
                    'Select both a Stage / Status Field and a Stage / Status Value.'
                ))
            if rec.stage_field_id.model_id != rec.model_id:
                raise ValidationError(_(
                    'The selected stage/status field does not belong to this model.'
                ))
            if rec.stage_field_id.ttype not in ('selection', 'many2one'):
                raise ValidationError(_(
                    'Stage/status fields must be Selection or Many2one fields.'
                ))
            if rec.stage_option_id and rec.stage_option_id.field_id != rec.stage_field_id:
                raise ValidationError(_(
                    'The chosen stage/status value belongs to a different field.'
                ))
            for line in rec.stage_approver_line_ids:
                if line.stage_option_id.field_id != rec.stage_field_id:
                    raise ValidationError(_(
                        'A stage approver row references a different stage field.'
                    ))

    def _stage_option_commands(self):
        """Pre-fill one row per stage; leave user choice to the manager."""
        self.ensure_one()
        if not self.stage_field_id:
            return []
        options = self.env['professional.approval.stage.option'].sudo().refresh_for_field(
            self.stage_field_id.id
        )
        return [(0, 0, {
            'stage_option_id': option.id, 'sequence': (index + 1) * 10,
            'required': True,
        }) for index, option in enumerate(options)]

    @api.onchange('use_stage_approvers')
    def _onchange_use_stage_approvers(self):
        if self.use_stage_approvers:
            self.stage_option_id = False
            if self.stage_field_id and not self.stage_approver_line_ids:
                self.stage_approver_line_ids = self._stage_option_commands()

    @api.onchange('stage_field_id')
    def _onchange_stage_field_id(self):
        self.stage_option_id = False
        # Changing a field invalidates assignments from the old field.
        self.stage_approver_line_ids = [(5, 0, 0)]
        if self.stage_field_id:
            if self.use_stage_approvers:
                self.stage_approver_line_ids = self._stage_option_commands()
            else:
                self.env['professional.approval.stage.option'].sudo().refresh_for_field(
                    self.stage_field_id.id
                )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.button_id = False
        self.stage_field_id = False
        self.stage_option_id = False
        self.stage_approver_line_ids = [(5, 0, 0)]
        self.use_stage_approvers = False
        domain = [('id', '=', False)]
        if self.model_id:
            self.env['professional.approval.button'].sudo().refresh_model_buttons(
                self.model_id.id
            )
            domain = [('model_id', '=', self.model_id.id)]
            # Pick the model's most likely statusbar field automatically.
            # The manager may change this field if the view uses another one.
            fields = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', self.model_id.id),
                ('ttype', 'in', ['selection', 'many2one']),
                ('name', 'in', ['state', 'stage_id', 'status', 'status_id',
                               'stage', 'x_stage_id', 'x_status']),
            ])
            detected = self.env['ir.model.fields']
            for preferred in (
                'state', 'stage_id', 'status', 'status_id',
                'stage', 'x_stage_id', 'x_status',
            ):
                detected = fields.filtered(lambda item: item.name == preferred)[:1]
                if detected:
                    break
            if not detected:
                # Studio/custom models often have x_ names. Do not confuse
                # an address state_id with a workflow stage.
                custom_candidates = self.env['ir.model.fields'].sudo().search([
                    ('model_id', '=', self.model_id.id),
                    ('ttype', 'in', ['selection', 'many2one']),
                    '|', ('name', 'ilike', 'stage'),
                    ('name', 'ilike', 'status'),
                ], order='name, id', limit=10)
                detected = custom_candidates[:1]
            if detected:
                self.stage_field_id = detected
                self.use_stage_approvers = True
                self.stage_approver_line_ids = self._stage_option_commands()
        return {'domain': {'button_id': domain}}

    def action_load_stage_options(self):
        """Load missing stages without overwriting existing approver choices."""
        self.ensure_one()
        if not self.stage_field_id:
            raise ValidationError(_('Select a Stage / Status Field first.'))
        options = self.env['professional.approval.stage.option'].sudo().refresh_for_field(
            self.stage_field_id.id
        )
        present = set(self.stage_approver_line_ids.mapped('stage_option_id').ids)
        additions = [(0, 0, {
            'stage_option_id': option.id, 'sequence': (i + 1) * 10,
        }) for i, option in enumerate(options) if option.id not in present]
        if additions:
            self.write({'stage_approver_line_ids': additions})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Stages Loaded'),
                           'message': _('Available stages are ready for approver selection.'),
                           'type': 'success', 'sticky': False}}

    def action_refresh_buttons(self):
        for rec in self:
            if rec.model_id:
                self.env['professional.approval.button'].sudo().refresh_model_buttons(
                    rec.model_id.id
                )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Buttons Refreshed'),
                'message': _('Object buttons were refreshed from the selected model form views.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Requests'),
            'res_model': 'professional.approval.request',
            'view_mode': 'list,form',
            'domain': [('rule_id', '=', self.id)],
            'context': {'default_rule_id': self.id},
        }

    def _domain_is_empty(self):
        self.ensure_one()
        return not self.condition_domain or self.condition_domain.strip() in ('[]', 'False', 'false')

    def _record_matches_condition(self, record):
        self.ensure_one()
        if self._domain_is_empty():
            return True
        try:
            domain = ast.literal_eval(self.condition_domain)
            expression.normalize_domain(domain)
        except Exception as exc:
            _logger.warning('Invalid approval domain on rule %s: %s', self.id, exc)
            return False
        return bool(record.sudo().search_count(expression.AND([domain, [('id', '=', record.id)]])))

    def _current_stage_value(self, record):
        """The technical stage/status key of this particular document."""
        self.ensure_one()
        if not self.stage_field_id or self.stage_field_id.name not in record._fields:
            return False
        current = record.sudo()[self.stage_field_id.name]
        if self.stage_field_id.ttype == 'many2one':
            return str(current.id) if current else ''
        return str(current) if current is not None else ''

    def _configured_stage_approvers(self, record):
        """Return only actual assigned users for the document's current stage."""
        self.ensure_one()
        if not self.use_stage_approvers:
            return self.env['professional.approval.stage.approver']
        value = self._current_stage_value(record)
        if value is False:
            return self.env['professional.approval.stage.approver']
        return self._configured_stage_approvers_for_value(value)

    def _configured_stage_approvers_for_value(self, value):
        self.ensure_one()
        if not self.use_stage_approvers or value is False or value is None:
            return self.env['professional.approval.stage.approver']
        value = str(value)
        return self.stage_approver_line_ids.filtered(
            lambda line: line.user_id and line.stage_option_id.value == value
        )

    def _stage_matches(self, record):
        """Stage assignments take precedence over the legacy single-stage rule."""
        self.ensure_one()
        if self.use_stage_approvers:
            return bool(self._configured_stage_approvers(record))
        if not self.stage_field_id or not self.stage_option_id:
            return True
        return self._current_stage_value(record) == self.stage_option_id.value

    def _stage_transition_method_name(self, field_name, target_value):
        self.ensure_one()
        return '__stage_write__::%s::%s' % (field_name, target_value)

    def _find_stage_transition_rule(self, record, field_name, target_value):
        model = self.env['ir.model'].sudo().search([('model', '=', record._name)], limit=1)
        domain = [
            ('active', '=', True),
            ('use_stage_approvers', '=', True),
            ('model_name', '=', record._name),
        ]
        if model:
            domain = [
                ('active', '=', True),
                ('use_stage_approvers', '=', True),
                '|',
                ('model_name', '=', record._name),
                ('model_id', '=', model.id),
            ]
        rules = self.sudo().search(domain, order='sequence, id')
        if not rules:
            return False

        record_company = False
        if 'company_id' in record._fields:
            record_company = record.company_id
        if not record_company:
            record_company = self.env.company

        def _matches_company(rule):
            if rule.company_ids:
                return record_company in rule.company_ids
            if rule.company_id:
                return rule.company_id == record_company
            return True

        rules = rules.filtered(_matches_company).filtered(
            lambda r: r.stage_field_id and r.stage_field_id.name == field_name
            and bool(r._configured_stage_approvers_for_value(target_value))
        )
        if not rules:
            return False

        current_user = self.env.user
        explicit = rules.filtered(lambda r: current_user.id in r.initiator_ids.ids)
        global_rules = rules.filtered(lambda r: not r.initiator_ids)
        for bucket in (explicit, global_rules):
            company_specific = bucket.filtered(
                lambda r: bool(r.company_ids) or bool(r.company_id)
            )
            company_global = bucket - company_specific
            for scoped_bucket in (company_specific, company_global):
                conditional = scoped_bucket.filtered(
                    lambda r: not r._domain_is_empty() and r._record_matches_condition(record)
                )
                if conditional:
                    return conditional[0]
                fallback = scoped_bucket.filtered(lambda r: r._domain_is_empty())
                if fallback:
                    return fallback[0]
        return False

    @api.model
    def _find_rule(self, record, method_name):
        model = self.env['ir.model'].sudo().search([('model', '=', record._name)], limit=1)
        domain = [
            ('active', '=', True),
            ('method_name', '=', method_name),
            ('model_name', '=', record._name),
        ]
        if model:
            domain = [
                ('active', '=', True),
                ('method_name', '=', method_name),
                '|',
                ('model_name', '=', record._name),
                ('model_id', '=', model.id),
            ]
        rules = self.sudo().search(domain, order='sequence, id')
        if not rules:
            return False

        record_company = False
        if 'company_id' in record._fields:
            record_company = record.company_id
        if not record_company:
            record_company = self.env.company

        def _matches_company(rule):
            if rule.company_ids:
                return record_company in rule.company_ids
            if rule.company_id:
                return rule.company_id == record_company
            return True

        rules = rules.filtered(_matches_company)
        if not rules:
            return False

        current_user = self.env.user
        explicit = rules.filtered(lambda r: current_user.id in r.initiator_ids.ids)
        global_rules = rules.filtered(lambda r: not r.initiator_ids)
        for bucket in (explicit, global_rules):
            company_specific = bucket.filtered(
                lambda r: bool(r.company_ids) or bool(r.company_id)
            )
            company_global = bucket - company_specific
            for scoped_bucket in (company_specific, company_global):
                # A stage-specific rule wins over a stage-agnostic rule in the
                # same user/company scope. Existing domain-specific rules keep
                # priority over domain-free rules within each stage scope.
                for stage_specific in (True, False):
                    matching = scoped_bucket.filtered(
                        lambda r: bool(r.stage_option_id or r.use_stage_approvers) == stage_specific
                        and r._stage_matches(record)
                    )
                    conditional = matching.filtered(
                        lambda r: not r._domain_is_empty()
                        and r._record_matches_condition(record)
                    )
                    if conditional:
                        return conditional[0]
                    fallback = matching.filtered(lambda r: r._domain_is_empty())
                    if fallback:
                        return fallback[0]
        return False

    @api.model
    def _install_method_wrappers(self, model_name):
        rules = self.sudo().search([
            ('active', '=', True),
            ('model_name', '=', model_name),
        ])
        if rules:
            self._install_state_write_wrapper(model_name)
        for method_name in set(rules.filtered('method_name').mapped('method_name')):
            self._install_method_wrapper(model_name, method_name)

    @api.model
    def _install_state_write_wrapper(self, model_name):
        """Invalidate approvals on cancel/reset without bypassing mail.thread.

        Do not override ``base.write`` globally. A global base-level write
        override can sit below ``mail.thread`` in the model MRO and make native
        tracked-field logging disappear on business documents. Instead, wrap
        the resolved ``write`` method only for models which actually have an
        active Dynamic Approval rule. Calling that resolved method preserves
        the complete native Odoo write chain, including ``mail.thread.write``.
        """
        if not model_name:
            return False
        try:
            model = self.env[model_name]
        except KeyError:
            return False

        model_cls = type(model)
        original = getattr(model_cls, 'write', None)
        if (
            not callable(original)
            or getattr(original, '_professional_state_write_wrapped', False)
        ):
            return False

        @wraps(original)
        def approval_state_write(records, vals):
            should_check = (
                isinstance(vals, dict)
                and 'state' in vals
                and bool(records)
                and 'state' in records._fields
                and not records.env.context.get(
                    '_professional_approval_invalidation'
                )
            )
            previous_states = (
                {record.id: record.state for record in records}
                if should_check
                else {}
            )

            approved_stage_requests = records.env['professional.approval.request']
            if (
                isinstance(vals, dict)
                and vals
                and bool(records)
                and not records.env.context.get('_professional_approval_bypass')
                and not records.env.context.get('_professional_approval_execution')
            ):
                Request = records.env['professional.approval.request']
                Rule = records.env['professional.approval.rule']
                for record in records:
                    for field_name, target_raw in vals.items():
                        if field_name not in record._fields:
                            continue
                        rule = Rule._find_stage_transition_rule(record, field_name, target_raw)
                        if not rule:
                            continue
                        current_value = rule._current_stage_value(record)
                        target_value = str(target_raw.id) if hasattr(target_raw, 'id') else str(target_raw)
                        if current_value == target_value:
                            continue
                        method_name = rule._stage_transition_method_name(field_name, target_value)
                        target_option = rule.stage_approver_line_ids.filtered(
                            lambda l: l.stage_option_id.value == target_value
                        )[:1].stage_option_id
                        target_label = target_option.name or target_value

                        approved_request = Request.sudo().search([
                            ('source_model', '=', record._name),
                            ('source_id', '=', record.id),
                            ('method_name', '=', method_name),
                            ('state', '=', 'approved'),
                            ('approval_consumed', '=', False),
                        ], order='id desc', limit=1)
                        if approved_request:
                            approved_stage_requests |= approved_request
                            continue

                        pending_request = Request.get_active_request(record._name, record.id, method_name)
                        if pending_request:
                            raise ValidationError(_(
                                'Approval is pending to change %s to %s. Waiting for: %s'
                            ) % (
                                rule.stage_field_id.field_description or field_name,
                                target_label,
                                pending_request.next_approver_names or _('approver'),
                            ))

                        request = Request.create_from_rule(
                            rule, record, method_name,
                            stage_value=target_value,
                            button_label=_('Change %(field)s to %(value)s') % {
                                'field': rule.stage_field_id.field_description or field_name,
                                'value': target_label,
                            },
                        )
                        raise ValidationError(_(
                            'Approval request created to change %s to %s. Waiting for: %s'
                        ) % (
                            rule.stage_field_id.field_description or field_name,
                            target_label,
                            request.next_approver_names or _('approver'),
                        ))

            # This is the model's normal resolved write method. For chatter
            # models it passes through mail.thread.write(), so all standard
            # Odoo tracking/subtypes remain exactly as they are by default.
            result = original(records, vals)

            if approved_stage_requests:
                approved_stage_requests.with_context(
                    _professional_approval_invalidation=True
                ).write({'approval_consumed': True})

            if not should_check:
                return result

            cancel_states = {'cancel', 'cancelled', 'canceled'}
            reset_record_ids = []
            for record in records:
                previous_state = previous_states.get(record.id)
                current_state = record.state
                is_cancel = (
                    current_state in cancel_states
                    and current_state != previous_state
                )
                is_reset_to_draft = (
                    current_state == 'draft'
                    and previous_state not in (False, 'draft')
                )
                if is_cancel or is_reset_to_draft:
                    reset_record_ids.append(record.id)

            if not reset_record_ids:
                return result

            request_model = records.env.registry.get(
                'professional.approval.request'
            )
            request_table = (
                getattr(request_model, '_table', False)
                if request_model
                else False
            )
            if not request_table:
                return result

            requests = records.env[
                'professional.approval.request'
            ].sudo().search([
                ('source_model', '=', records._name),
                ('source_id', 'in', reset_record_ids),
                ('state', '=', 'approved'),
                ('approval_consumed', '=', False),
            ])
            if requests:
                requests.with_context(
                    _professional_approval_invalidation=True
                ).write({'approval_consumed': True})

            return result

        approval_state_write._professional_state_write_wrapped = True
        setattr(model_cls, 'write', approval_state_write)
        return True

    @api.model
    def _install_method_wrapper(self, model_name, method_name):
        if not method_name or method_name.startswith('_'):
            return False
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        model_cls = type(model)
        original = getattr(model_cls, method_name, None)
        if not callable(original) or getattr(original, '_professional_approval_wrapped', False):
            return False

        @wraps(original)
        def approval_wrapped(records, *args, **kwargs):
            if not records.env.context.get('_professional_approval_bypass'):
                for rec in records:
                    action = rec._professional_check_approval(method_name)
                    if action:
                        return action

            # A completed approval remains valid for the protected action as
            # long as the document isn't cancelled/reset to draft. The generic
            # base.write() hook is the only place that invalidates an approved
            # request, and only when the record's state genuinely changes to
            # cancel/draft - including when that very transition is caused by
            # this protected method itself (e.g. an approval-protected Cancel
            # or Reset to Draft button). It must NOT be skipped just because
            # we're inside this bypass context, otherwise cancelling/resetting
            # a protected document would never clear other buttons' already
            # used approvals.
            execution_context = dict(records.env.context)
            # Preserve normal Odoo mail.thread tracking when the protected
            # business action changes state. Approval UI/navigation contexts
            # must not leak tracking suppression into the native method.
            execution_context.pop('tracking_disable', None)
            execution_context.pop('mail_notrack', None)
            execution_context.update({
                '_professional_approval_bypass': True,
                '_professional_approval_execution': True,
            })
            execution_records = records.with_context(execution_context)

            # Execute the original business method through Odoo's untouched
            # native model chain. mail.thread.write() will prepare and finalize
            # its own tracked values at pre-commit, exactly as standard Odoo 19
            # does when Dynamic Approval is not installed.
            return original(execution_records, *args, **kwargs)

        approval_wrapped._professional_approval_wrapped = True
        setattr(model_cls, method_name, approval_wrapped)
        return True
