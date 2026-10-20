from odoo import api, fields, models

from .sequence_support import (
    get_next_sequence_value,
    get_sequence_date,
    PLACEHOLDER_VALUES,
)


class AccountMove(models.Model):
    _inherit = "account.move"

    conditional_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Applied Conditional Sequence",
        copy=False,
        readonly=True,
        index=True,
    )

    def _get_current_conditional_sequence(self, allow_fallback=True):
        self.ensure_one()
        company = self.company_id or self.env.company
        return (
            self.env["ir.sequence"]
            .with_company(company)
            ._get_for_record(self, allow_fallback=allow_fallback)
        )

    def _apply_current_conditional_sequence(self, force=False):
        """Apply the sequence that matches the move's CURRENT values.

        Draft rules therefore apply on draft save. If another rule later matches
        (for example state = posted), a new number is generated from that rule.
        Re-writing the same matching rule does not consume another number.
        """
        for move in self:
            if move.env.context.get("skip_conditional_sequence"):
                continue

            sequence = move._get_current_conditional_sequence()
            if not sequence:
                continue

            if not force and move.conditional_sequence_id == sequence:
                continue

            sequence_date = get_sequence_date(move)
            new_name = get_next_sequence_value(
                sequence, move, sequence_date=sequence_date
            )
            move.with_context(skip_conditional_sequence=True).write(
                {
                    "name": new_name,
                    "conditional_sequence_id": sequence.id,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        # Respect a deliberately supplied accounting number. Otherwise apply
        # the rule matching the newly saved move (normally state = draft).
        for move, vals in zip(moves, vals_list):
            supplied_name = vals.get("name")
            if supplied_name and supplied_name not in PLACEHOLDER_VALUES:
                continue
            move._apply_current_conditional_sequence()

        return moves

    def write(self, vals):
        if self.env.context.get("skip_conditional_sequence"):
            return super().write(vals)

        companies = {
            move.id: (move.company_id or self.env.company)
            for move in self
        }
        old_sequence_ids = {
            move.id: move.conditional_sequence_id.id
            for move in self
        }

        result = super().write(vals)

        changed_fields = set(vals)
        sequence_env = self.env["ir.sequence"]

        for move in self:
            company = companies.get(move.id) or move.company_id or self.env.company
            watched = sequence_env.with_company(company)._get_watched_fields(
                move._name,
                company,
            )
            if not (changed_fields & watched):
                continue

            sequence = move._get_current_conditional_sequence()
            if not sequence:
                continue

            # Only consume a new number when the matching rule actually changed.
            if old_sequence_ids.get(move.id) == sequence.id:
                continue

            move._apply_current_conditional_sequence(force=True)

        return result

    def _set_next_sequence(self):
        """Coordinate with Odoo's native accounting numbering while posting.

        - If the CURRENT (usually posted) values match a conditional rule, use it.
        - If a draft conditional number was already applied and no new explicit
          posted rule matches, keep that number.
        - Otherwise use Odoo's standard journal sequence unchanged.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        seq_env = self.env["ir.sequence"].with_company(company)

        explicit_sequence = seq_env._get_for_record(self, allow_fallback=False)
        if explicit_sequence:
            if self.conditional_sequence_id != explicit_sequence:
                self.name = get_next_sequence_value(
                    explicit_sequence,
                    self,
                    sequence_date=get_sequence_date(self),
                )
                self.conditional_sequence_id = explicit_sequence
            return

        if self.conditional_sequence_id and self.name not in PLACEHOLDER_VALUES:
            # A previous state (for example Draft) intentionally assigned this
            # number. Do not let native posting overwrite it when there is no
            # matching rule for the new state.
            return

        fallback_sequence = seq_env._get_for_record(self, allow_fallback=True)
        if fallback_sequence:
            self.name = get_next_sequence_value(
                fallback_sequence,
                self,
                sequence_date=get_sequence_date(self),
            )
            self.conditional_sequence_id = fallback_sequence
            return

        return super()._set_next_sequence()
