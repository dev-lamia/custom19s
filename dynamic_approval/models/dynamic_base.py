import logging

from lxml import etree

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ProfessionalApprovalBase(models.AbstractModel):
    _inherit = 'base'

    def _professional_table_ready(self, model_name):
        """Return whether a model table is available during registry loading."""
        model_class = self.env.registry.get(model_name)
        if not model_class:
            return False
        table = getattr(model_class, '_table', False)
        if not table:
            return False
        with self.env.cr.savepoint():
            self.env.cr.execute('SELECT to_regclass(%s)', (table,))
            return bool(self.env.cr.fetchone()[0])

    def _approval_popup(self, title, message):
        popup = self.env['professional.approval.popup'].sudo().create({
            'message': message,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Approval'),
            'res_model': 'professional.approval.popup',
            'res_id': popup.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _professional_source_action(self):
        """Reopen the same source record and force a fresh form architecture."""
        self.ensure_one()
        action_context = dict(self.env.context)
        # Never carry mail tracking suppression into the reopened business
        # document. Otherwise a later state change can silently skip Chatter
        # tracking even though the native field is tracked.
        action_context.pop('tracking_disable', None)
        action_context.pop('mail_notrack', None)
        action_context.update({
            'active_id': self.id,
            'active_ids': [self.id],
            'res_id': self.id,
            'professional_source_id': self.id,
            'professional_refresh_token': fields.Datetime.now().isoformat(),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.display_name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': action_context,
        }

    def _professional_check_approval(self, method_name):
        if not self:
            return False
        self.ensure_one()
        if self.env.context.get('_professional_approval_bypass'):
            return False

        if not self._professional_table_ready('professional.approval.request'):
            return False
        Request = self.env['professional.approval.request']
        request = Request.get_active_request(self._name, self.id, method_name)
        if request:
            result = request._try_approve(self.env.user)
            if result == 'not_approver':
                return self._approval_popup(
                    _('Approval Needed'),
                    _('Approval needed for "%s". You are not an assigned approver.')
                    % self.display_name,
                )
            if result == 'not_turn':
                return self._approval_popup(
                    _('Approval Needed'),
                    _('It is not your turn yet. Waiting for: %s')
                    % (request.next_approver_names or _('previous approver')),
                )
            if result == 'already':
                return self._approval_popup(
                    _('Already Approved'),
                    _('You already approved "%s".') % self.display_name,
                )
            # Approval and the original business action are deliberately two
            # separate clicks. Reopen the form so the next approver sees
            # Approve, or the native button returns after final approval.
            return self._professional_source_action()

        approved_request = Request.sudo().search([
            ('source_model', '=', self._name),
            ('source_id', '=', self.id),
            ('method_name', '=', method_name),
            ('state', '=', 'approved'),
            ('approval_consumed', '=', False),
        ], order='id desc', limit=1)
        if approved_request:
            return False

        if not self._professional_table_ready('professional.approval.rule'):
            return False
        rule = self.env['professional.approval.rule']._find_rule(self, method_name)
        if not rule:
            return False
        request = Request.create_from_rule(rule, self, method_name)
        if request._user_can_approve(self.env.user):
            return self._professional_check_approval(method_name)
        return self._approval_popup(
            _('Approval Required'),
            _('Approval request created for "%s". Waiting for: %s') % (
                self.display_name,
                request.next_approver_names or _('approver'),
            ),
        )

    def action_professional_approve(self):
        """Approve the pending request represented by the temporary UI button."""
        self.ensure_one()
        method_name = self.env.context.get('professional_method_name')
        if not method_name:
            return self._approval_popup(
                _('Approval'),
                _('The protected action could not be identified. Refresh the form.'),
            )
        if not self._professional_table_ready('professional.approval.request'):
            return self._approval_popup(
                _('Approval'),
                _('Approval data is not ready. Please refresh the page.'),
            )

        request = self.env['professional.approval.request'].get_active_request(
            self._name,
            self.id,
            method_name,
        )
        if not request:
            return self._professional_source_action()

        result = request._try_approve(self.env.user)
        if result == 'not_approver':
            return self._approval_popup(
                _('Approval'),
                _('You are not an assigned approver for this request.'),
            )
        if result == 'not_turn':
            return self._approval_popup(
                _('Approval'),
                _('It is not your turn yet. Waiting for: %s')
                % (request.next_approver_names or _('previous approver')),
            )
        if result == 'already':
            return self._approval_popup(
                _('Approval'),
                _('You already approved this request.'),
            )
        return self._professional_source_action()


    @api.model
    def professional_button_states(self, record_id):
        """Return protected button labels for the current form record.

        The form architecture is cached by Odoo and cannot safely be changed
        per record. The web client uses this lightweight endpoint to display
        ``Approve`` only while the logged-in user has a waiting approval line.
        """
        if not record_id or not self._professional_table_ready(
            'professional.approval.rule'
        ):
            return []

        rules = self.env['professional.approval.rule'].sudo().search([
            ('active', '=', True),
            ('model_name', '=', self._name),
            ('method_name', '!=', False),
        ])
        if not rules:
            return []

        requests = self.env['professional.approval.request'].sudo().search([
            ('source_model', '=', self._name),
            ('source_id', '=', int(record_id)),
            ('state', '=', 'pending'),
            ('method_name', 'in', rules.mapped('method_name')),
        ])
        request_by_method = {request.method_name: request for request in requests}
        result = []
        for rule in rules:
            request = request_by_method.get(rule.method_name)
            pending_for_user = False
            if request:
                user_line = request.line_ids.filtered(
                    lambda line: line.user_id.id == self.env.uid
                    and line.status == 'waiting'
                )[:1]
                if user_line:
                    pending_for_user = True
                    if rule.sequential_approval:
                        blockers = request.line_ids.filtered(
                            lambda line: line.sequence < user_line.sequence
                            and line.status == 'waiting'
                        )
                        pending_for_user = not bool(blockers)
            result.append({
                'method_name': rule.method_name,
                'normal_label': rule.button_id.button_label or rule.method_name,
                'pending_for_user': pending_for_user,
            })
        return result

    @api.model
    def _professional_context_record_id(self):
        """Best-effort current record id from web-client action context."""
        context = self.env.context
        for key in ('professional_source_id', 'active_id', 'res_id'):
            value = context.get(key)
            if isinstance(value, int) and value > 0:
                return value
        params = context.get('params') or {}
        if isinstance(params, dict):
            for key in ('id', 'resId', 'res_id'):
                value = params.get(key)
                if isinstance(value, int) and value > 0:
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return False

    @api.model
    def _professional_approval_methods_for_user(self):
        """Methods currently awaiting approval from the logged-in user."""
        if not self._professional_table_ready('professional.approval.request'):
            return set()

        domain = [
            ('source_model', '=', self._name),
            ('state', '=', 'pending'),
            ('line_ids.user_id', '=', self.env.uid),
            ('line_ids.status', '=', 'waiting'),
        ]
        record_id = self._professional_context_record_id()
        # A form architecture can be cached and reused for many records. Never
        # rename a native button based only on another pending request from the
        # same model, because an already-approved document would then still
        # display Approve. Patch only when the current source record is known.
        if not record_id:
            return set()
        domain.append(('source_id', '=', record_id))

        requests = self.env['professional.approval.request'].sudo().search(domain)
        methods = set()
        for request in requests:
            user_line = request.line_ids.filtered(
                lambda line: line.user_id.id == self.env.uid
                and line.status == 'waiting'
            )[:1]
            if not user_line:
                continue
            if request.rule_id.sequential_approval:
                blocker = request.line_ids.filtered(
                    lambda line: line.sequence < user_line.sequence
                    and line.status == 'waiting'
                )
                if blocker:
                    continue
            methods.add(request.method_name)
        return methods

    @api.model
    def _patch_professional_button_labels(self, arch):
        """Replace only protected native buttons with a safe Approve action."""
        methods = self._professional_approval_methods_for_user()
        if not methods or not arch:
            return arch
        try:
            root = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
        except (TypeError, ValueError, etree.XMLSyntaxError):
            return arch

        changed = False
        for node in root.xpath("//button[@type='object'][@name]"):
            method_name = node.get('name')
            if method_name not in methods:
                continue
            node.set('name', 'action_professional_approve')
            node.set('string', _('Approve'))
            node.set(
                'context',
                "{'professional_method_name': %r}" % method_name,
            )
            node.set('class', 'btn-primary')
            changed = True

        if not changed:
            return arch
        return etree.tostring(root, encoding='unicode')

    def _patch_professional_view(self, result):
        try:
            with self.env.cr.savepoint():
                if self._professional_table_ready('professional.approval.rule'):
                    self.env['professional.approval.rule']._install_method_wrappers(
                        self._name
                    )
        except Exception:
            _logger.debug(
                'Professional approval wrapper skipped for %s',
                self._name,
                exc_info=True,
            )
        return result

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        self._patch_professional_view(result)
        form_view = (
            result.get('views', {}).get('form')
            if isinstance(result, dict)
            else False
        )
        if form_view and form_view.get('arch'):
            form_view['arch'] = self._patch_professional_button_labels(
                form_view['arch']
            )
        return result

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(
            view_id=view_id,
            view_type=view_type,
            **options,
        )
        if view_type == 'form':
            self._patch_professional_view(result)
            if isinstance(result, dict) and result.get('arch'):
                result['arch'] = self._patch_professional_button_labels(
                    result['arch']
                )
        return result
