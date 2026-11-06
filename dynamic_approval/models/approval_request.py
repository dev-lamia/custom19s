from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProfessionalApprovalRequestLine(models.Model):
    _name = 'professional.approval.request.line'
    _description = 'Approval Request Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'professional.approval.request',
        string='Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one('res.users', string='Approver', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    required = fields.Boolean(string='Required', default=True)
    status = fields.Selection(
        [('waiting', 'Waiting'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        string='Status',
        default='waiting',
        required=True,
        tracking=True,
    )
    approved_date = fields.Datetime(string='Approved On', readonly=True)


class ProfessionalApprovalRequest(models.Model):
    _name = 'professional.approval.request'
    _description = 'Dynamic Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Request Reference', required=True, copy=False, default='New')
    rule_id = fields.Many2one(
        'professional.approval.rule',
        string='Approval Rule',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
        index=True,
    )
    request_owner_id = fields.Many2one(
        'res.users',
        string='Initiator',
        default=lambda self: self.env.user,
        required=True,
        index=True,
        tracking=True,
    )
    source_model = fields.Char(string='Source Model', required=True, readonly=True, index=True)
    source_id = fields.Integer(string='Source ID', required=True, readonly=True, index=True)
    source_name = fields.Char(string='Source Record', readonly=True)
    method_name = fields.Char(string='Method Name', required=True, readonly=True, index=True)
    button_label = fields.Char(string='Button', readonly=True)
    approval_consumed = fields.Boolean(
        string='Approval Used',
        default=False,
        copy=False,
        readonly=True,
        index=True,
    )
    line_ids = fields.One2many(
        'professional.approval.request.line',
        'request_id',
        string='Approvers',
        copy=False,
    )
    approved_count = fields.Integer(string='Approved', compute='_compute_counts')
    required_count = fields.Integer(string='Required', compute='_compute_counts')
    next_approver_names = fields.Char(string='Next Approvers', compute='_compute_next_approvers')

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = sequence.next_by_code('professional.approval.request') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.status', 'line_ids.required')
    def _compute_counts(self):
        for rec in self:
            rec.approved_count = len(rec.line_ids.filtered(lambda l: l.status == 'approved'))
            rec.required_count = len(rec.line_ids)

    @api.depends('line_ids.status', 'line_ids.sequence', 'rule_id.sequential_approval')
    def _compute_next_approvers(self):
        for rec in self:
            waiting = rec.line_ids.filtered(lambda l: l.status == 'waiting')
            if rec.rule_id.sequential_approval and waiting:
                min_seq = min(waiting.mapped('sequence'))
                waiting = waiting.filtered(lambda l: l.sequence == min_seq)
            rec.next_approver_names = ', '.join(waiting.mapped('user_id.name'))

    @api.model
    def get_active_request(self, source_model, source_id, method_name):
        return self.sudo().search([
            ('source_model', '=', source_model),
            ('source_id', '=', source_id),
            ('method_name', '=', method_name),
            ('state', '=', 'pending'),
        ], order='id desc', limit=1)

    @api.model
    def create_from_rule(self, rule, record, method_name):
        request = self.sudo().create({
            'rule_id': rule.id,
            'source_model': record._name,
            'source_id': record.id,
            'source_name': record.display_name,
            'method_name': method_name,
            'button_label': rule.button_id.button_label or method_name,
            'request_owner_id': self.env.user.id,
        })
        for approver in rule.approver_line_ids:
            self.env['professional.approval.request.line'].sudo().create({
                'request_id': request.id,
                'user_id': approver.user_id.id,
                'sequence': approver.sequence,
                'required': approver.required,
                'status': 'waiting',
            })
        request._send_activity_to_first()
        request._post_source_message(_('Approval requested for %s.') % request.button_label)
        return request

    def _source_record(self):
        self.ensure_one()
        try:
            record = self.env[self.source_model].browse(self.source_id)
            return record if record.exists() else self.env[self.source_model].browse()
        except Exception:
            return self.env[self._name].browse()


    def action_open_source(self):
        self.ensure_one()
        record = self._source_record()
        if not record:
            raise UserError(_('Source record was not found.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.source_name or _('Source Document'),
            'res_model': self.source_model,
            'res_id': self.source_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_approve(self):
        self.ensure_one()
        if self.state != 'pending':
            return self.action_open_source()
        result = self._try_approve(self.env.user)
        if result == 'not_approver':
            raise UserError(_('You are not an assigned approver for this request.'))
        if result == 'not_turn':
            raise UserError(
                _('It is not your turn yet. Waiting for: %s')
                % (self.next_approver_names or _('previous approver'))
            )
        if result == 'already':
            raise UserError(_('You already approved this request.'))
        if result == 'completed':
            # Approval completion and the original business action are separate
            # user actions. Open the source document without executing the
            # protected method (Send RFQ, Confirm, Validate, etc.).
            return self.action_open_source()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Request'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _post_source_message(self, body):
        self.ensure_one()
        record = self._source_record()
        if record and hasattr(record, 'message_post'):
            record.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')

    def _waiting_lines_for_activity(self):
        self.ensure_one()
        waiting = self.line_ids.filtered(lambda l: l.status == 'waiting')
        if self.rule_id.sequential_approval and waiting:
            min_seq = min(waiting.mapped('sequence'))
            waiting = waiting.filtered(lambda l: l.sequence == min_seq)
        return waiting

    def _send_activity_to_first(self):
        self.ensure_one()
        self._schedule_activities(self._waiting_lines_for_activity())

    def _schedule_activities(self, lines):
        self.ensure_one()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        # Important: assign the activity to the original business document
        # (PO/SO/etc.), not to the approval request. Then My Activities opens
        # P00014/S00067 directly and the approver can click the protected
        # button renamed as Approve on that full form.
        activity_record = self._source_record()
        if not activity_record or not hasattr(activity_record, 'activity_schedule'):
            activity_record = self

        summary = '✅ Approval Required — %s' % (self.button_label or self.method_name)
        for line in lines:
            existing = self.env['mail.activity'].sudo().search([
                '|',
                '&',
                ('res_model', '=', activity_record._name),
                ('res_id', '=', activity_record.id),
                '&',
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('user_id', '=', line.user_id.id),
                ('summary', '=', summary),
            ], limit=1)
            if existing:
                if (
                    existing.res_model != activity_record._name
                    or existing.res_id != activity_record.id
                ):
                    existing.sudo().write({
                        'res_model_id': self.env['ir.model']._get_id(
                            activity_record._name
                        ),
                        'res_id': activity_record.id,
                    })
                continue
            activity_record.activity_schedule(
                activity_type_id=activity_type.id,
                summary=summary,
                note=_(
                    '%(owner)s needs approval for %(record)s. '
                    'Open the document and click Approve.'
                ) % {
                    'owner': self.request_owner_id.name,
                    'record': self.source_name,
                },
                user_id=line.user_id.id,
            )

    def _schedule_completion_activity(self):
        self.ensure_one()
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo',
            raise_if_not_found=False,
        )
        if not activity_type or not self.request_owner_id:
            return

        activity_record = self._source_record()
        if not activity_record or not hasattr(activity_record, 'activity_schedule'):
            activity_record = self

        summary = '✅ Approval Completed — %s' % (
            self.button_label or self.method_name
        )
        existing = self.env['mail.activity'].sudo().search([
            ('res_model', '=', activity_record._name),
            ('res_id', '=', activity_record.id),
            ('user_id', '=', self.request_owner_id.id),
            ('summary', '=', summary),
        ], limit=1)
        if existing:
            return

        activity_record.sudo().activity_schedule(
            activity_type_id=activity_type.id,
            summary=summary,
            note=_(
                'The approval for %(record)s is complete. '
                'Open the document to continue.'
            ) % {
                'record': self.source_name,
            },
            user_id=self.request_owner_id.id,
        )

    def _close_user_activities(self, user):
        self.ensure_one()
        activities = self.env['mail.activity'].sudo().search([
            '|',
            '&', ('res_model', '=', self._name), ('res_id', '=', self.id),
            '&', ('res_model', '=', self.source_model), ('res_id', '=', self.source_id),
            ('user_id', '=', user.id),
            ('summary', 'ilike', 'Approval Required'),
        ])
        if activities:
            try:
                activities.action_feedback(feedback=_('Approved'))
            except Exception:
                activities.unlink()

    def _close_all_activities(self):
        self.ensure_one()
        activities = self.env['mail.activity'].sudo().search([
            '|',
            '&', ('res_model', '=', self._name), ('res_id', '=', self.id),
            '&', ('res_model', '=', self.source_model), ('res_id', '=', self.source_id),
            ('summary', 'ilike', 'Approval Required'),
        ])
        if activities:
            try:
                activities.action_feedback(feedback=_('Approval completed'))
            except Exception:
                activities.unlink()

    def _is_fully_approved(self):
        self.ensure_one()
        required_waiting = self.line_ids.filtered(lambda l: l.required and l.status != 'approved')
        if required_waiting:
            return False
        minimum = min(self.rule_id.minimum_approvals or len(self.line_ids), len(self.line_ids))
        return len(self.line_ids.filtered(lambda l: l.status == 'approved')) >= minimum

    def _user_can_approve(self, user):
        self.ensure_one()
        return bool(self.line_ids.filtered(lambda l: l.user_id.id == user.id))

    def _try_approve(self, user):
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.user_id.id == user.id)[:1]
        if not line:
            return 'not_approver'
        if line.status == 'approved':
            return 'already'
        if self.rule_id.sequential_approval:
            blockers = self.line_ids.filtered(
                lambda l: l.sequence < line.sequence and l.status == 'waiting'
            )
            if blockers:
                return 'not_turn'
        line.sudo().write({'status': 'approved', 'approved_date': fields.Datetime.now()})
        self._close_user_activities(user)
        if self._is_fully_approved():
            self.action_mark_approved()
            return 'completed'
        self._schedule_activities(self._waiting_lines_for_activity())
        return 'approved'

    def action_mark_approved(self):
        for rec in self:
            if rec.state != 'pending':
                continue
            rec.sudo().write({'state': 'approved'})
            rec._close_all_activities()
            rec._schedule_completion_activity()
            rec._post_source_message(_('Approval completed for %s.') % rec.button_label)

    def action_cancel(self):
        for rec in self:
            rec.sudo().write({'state': 'cancelled'})
            rec._close_all_activities()

    def action_reject(self):
        for rec in self:
            line = rec.line_ids.filtered(lambda l: l.user_id.id == self.env.uid)[:1]
            if not line:
                raise UserError(_('Only assigned approvers can reject this request.'))
            line.sudo().write({'status': 'rejected'})
            rec.sudo().write({'state': 'rejected'})
            rec._close_all_activities()
            rec._post_source_message(_('Approval rejected for %s.') % rec.button_label)
