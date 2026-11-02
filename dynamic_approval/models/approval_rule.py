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
        required=True,
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
                    ('method_name', '!=', False),
                ])
                for rule in rules:
                    rule._install_state_write_wrapper(rule.model_name)
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
        if {'active', 'model_id', 'button_id'} & set(vals):
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
            lambda rule: rule.active and rule.model_name and rule.method_name
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

    @api.constrains('approver_line_ids', 'minimum_approvals')
    def _check_approvers(self):
        for rec in self:
            if not rec.approver_line_ids:
                raise ValidationError(_('Please add at least one approver.'))
            if rec.minimum_approvals < 1:
                raise ValidationError(_('Minimum approvals must be at least 1.'))
            if rec.minimum_approvals > len(rec.approver_line_ids):
                raise ValidationError(_('Minimum approvals cannot exceed approver count.'))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.button_id = False
        domain = [('id', '=', False)]
        if self.model_id:
            self.env['professional.approval.button'].sudo().refresh_model_buttons(
                self.model_id.id
            )
            domain = [('model_id', '=', self.model_id.id)]
        return {'domain': {'button_id': domain}}

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
                conditional = scoped_bucket.filtered(
                    lambda r: not r._domain_is_empty()
                    and r._record_matches_condition(record)
                )
                if conditional:
                    return conditional[0]
                fallback = scoped_bucket.filtered(lambda r: r._domain_is_empty())
                if fallback:
                    return fallback[0]
        return False

    @api.model
    def _install_method_wrappers(self, model_name):
        rules = self.sudo().search([
            ('active', '=', True),
            ('model_name', '=', model_name),
            ('method_name', '!=', False),
        ])
        if rules:
            self._install_state_write_wrapper(model_name)
        for method_name in set(rules.mapped('method_name')):
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

            # This is the model's normal resolved write method. For chatter
            # models it passes through mail.thread.write(), so all standard
            # Odoo tracking/subtypes remain exactly as they are by default.
            result = original(records, vals)

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
