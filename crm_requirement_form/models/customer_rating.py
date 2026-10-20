from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CrmCustomerRating(models.Model):
    _name = 'crm.customer.rating'
    _description = 'Customer Ranking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    RANK_SELECTION = [
        ('a', 'A'),
        ('b', 'B'),
        ('c', 'C'),
    ]

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Optional CRM Lead/Opportunity linked to this ranking.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        index=True,
        tracking=True,
        ondelete='cascade',
        help='Customer being ranked. A ranking can be created directly from the Customer page.',
    )

    responsiveness_score = fields.Selection(
        RANK_SELECTION,
        string='Responsiveness',
        default='b',
        required=True,
        tracking=True,
    )
    behavior_score = fields.Selection(
        RANK_SELECTION,
        string='Behavior',
        default='b',
        required=True,
        tracking=True,
    )
    payment_on_time_score = fields.Selection(
        RANK_SELECTION,
        string='Payment on Time',
        default='b',
        required=True,
        tracking=True,
    )
    meeting_adherence_score = fields.Selection(
        RANK_SELECTION,
        string='Adherence to Meetings',
        default='b',
        required=True,
        tracking=True,
    )
    requirements_artwork_score = fields.Selection(
        RANK_SELECTION,
        string='Availability of Requirements and Artwork',
        default='b',
        required=True,
        tracking=True,
    )

    auto_rank = fields.Selection(
        selection=RANK_SELECTION,
        string='Form AVG Rank',
        compute='_compute_auto_rank',
        store=True,
        help='Calculated from the average of the five A/B/C rankings.',
    )
    customer_average_rank = fields.Selection(
        selection=RANK_SELECTION,
        string='Customer AVG',
        compute='_compute_customer_average_rank',
        help='Average ranking of this customer across design ranking forms.',
    )
    manual_rank = fields.Selection(
        selection=RANK_SELECTION,
        string='Final Rank Override',
        tracking=True,
        help='Leave empty to use the form average rank.',
    )
    rank = fields.Selection(
        selection=RANK_SELECTION,
        string='Final Rank',
        compute='_compute_rank',
        store=True,
        tracking=True,
    )
    notes = fields.Text(string='Ranking Notes')

    _sql_constraints = [
        (
            'crm_customer_rating_lead_unique',
            'unique(lead_id)',
            'Only one customer ranking is allowed per lead.',
        ),
    ]

    @api.depends('lead_id', 'partner_id', 'rank')
    def _compute_name(self):
        for rec in self:
            source_name = (
                rec.lead_id.display_name
                or rec.partner_id.display_name
                or _('Customer Ranking')
            )
            rank_label = dict(rec._fields['rank'].selection).get(rec.rank)
            rec.name = (
                f'{source_name} - Rank {rank_label}'
                if rank_label
                else source_name
            )

    @api.model_create_multi
    def create(self, vals_list):
        lead_ids = [vals.get('lead_id') for vals in vals_list if vals.get('lead_id')]
        leads_by_id = {lead.id: lead for lead in self.env['crm.lead'].browse(lead_ids)}
        for vals in vals_list:
            lead = leads_by_id.get(vals.get('lead_id'))
            if lead and lead.partner_id and not vals.get('partner_id'):
                vals['partner_id'] = lead.partner_id.id
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if 'lead_id' in vals and 'partner_id' not in vals:
            for rec in self.filtered(lambda item: item.lead_id and item.lead_id.partner_id):
                if rec.partner_id != rec.lead_id.partner_id:
                    super(CrmCustomerRating, rec).write({
                        'partner_id': rec.lead_id.partner_id.id,
                    })
        return result

    @api.onchange('lead_id')
    def _onchange_lead_id_set_partner(self):
        for rec in self:
            if rec.lead_id and rec.lead_id.partner_id:
                rec.partner_id = rec.lead_id.partner_id

    @api.constrains('lead_id', 'partner_id')
    def _check_ranking_source(self):
        for rec in self:
            if not rec.lead_id and not rec.partner_id:
                raise ValidationError(
                    _('Select a Customer or a Lead/Opportunity for the ranking.')
                )

    def _normalise_rank_value(self, value):
        """Support old numeric values from previous score-based versions."""
        if not value:
            return False
        if value in ('a', 'b', 'c'):
            return value
        if value in ('4', '5'):
            return 'a'
        if value in ('2', '3'):
            return 'b'
        return 'c'

    @api.model
    def _rank_to_weight(self, value):
        rank = self._normalise_rank_value(value)
        return {'a': 3, 'b': 2, 'c': 1}.get(rank, 0)

    @api.model
    def _rank_from_average(self, average):
        if average >= 2.5:
            return 'a'
        if average >= 1.5:
            return 'b'
        return 'c'

    def _get_question_ranks(self):
        self.ensure_one()
        return [
            self.responsiveness_score,
            self.behavior_score,
            self.payment_on_time_score,
            self.meeting_adherence_score,
            self.requirements_artwork_score,
        ]

    def _get_form_average_rank(self):
        self.ensure_one()
        weights = [self._rank_to_weight(value) for value in self._get_question_ranks()]
        valid_weights = [weight for weight in weights if weight]
        if not valid_weights:
            return False
        return self._rank_from_average(sum(valid_weights) / len(valid_weights))

    @api.depends(
        'responsiveness_score',
        'behavior_score',
        'payment_on_time_score',
        'meeting_adherence_score',
        'requirements_artwork_score',
    )
    def _compute_auto_rank(self):
        for rec in self:
            rec.auto_rank = rec._get_form_average_rank()

    @api.depends('auto_rank', 'manual_rank')
    def _compute_rank(self):
        for rec in self:
            rec.rank = rec.manual_rank or rec.auto_rank

    @api.depends('partner_id', 'lead_id', 'rank')
    def _compute_customer_average_rank(self):
        partner_ids = self.mapped('partner_id').ids
        lead_ids_without_partner = self.filtered(lambda item: not item.partner_id).mapped(
            'lead_id'
        ).ids

        ratings = self.env['crm.customer.rating'].search([
            '|',
            ('partner_id', 'in', partner_ids or [0]),
            ('lead_id', 'in', lead_ids_without_partner or [0]),
        ])

        weights_by_partner = {}
        weights_by_lead = {}
        for rating in ratings:
            weight = rating._rank_to_weight(rating.rank)
            if not weight:
                continue
            if rating.partner_id:
                weights_by_partner.setdefault(rating.partner_id.id, []).append(weight)
            else:
                weights_by_lead.setdefault(rating.lead_id.id, []).append(weight)

        for rec in self:
            if rec.partner_id:
                weights = weights_by_partner.get(rec.partner_id.id, [])
            else:
                weights = weights_by_lead.get(rec.lead_id.id, [])
            rec.customer_average_rank = (
                rec._rank_from_average(sum(weights) / len(weights)) if weights else False
            )
