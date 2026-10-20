from odoo import api, fields, models


class ConditionalSequenceCounter(models.Model):
    _name = "conditional.sequence.counter"
    _description = "Conditional Sequence Counter"
    _order = "sequence_id, counter_key, date_range_key"

    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Sequence",
        required=True,
        index=True,
        ondelete="cascade",
    )
    counter_key = fields.Char(
        string="Counter Key",
        required=True,
        index=True,
    )
    date_range_key = fields.Char(
        string="Date Range Key",
        required=True,
        default="global",
        index=True,
    )
    number_next = fields.Integer(
        string="Next Number",
        required=True,
        default=1,
    )

    _unique_sequence_counter = models.Constraint(
        "UNIQUE(sequence_id, counter_key, date_range_key)",
        "A counter already exists for this sequence, key, and date range.",
    )

    @api.model
    def _next_number(self, sequence, counter_key, sequence_date=None):
        """Return and increment a transaction-safe field-value-specific counter."""
        sequence.ensure_one()
        normalized_key = (counter_key or "").strip()
        if not normalized_key:
            return False

        date_range_key = "global"
        if sequence.use_date_range:
            current_sequence = sequence._get_current_sequence(
                sequence_date=sequence_date
            )
            if current_sequence._name == "ir.sequence.date_range":
                date_range_key = "%s:%s" % (
                    fields.Date.to_string(current_sequence.date_from),
                    fields.Date.to_string(current_sequence.date_to),
                )

        lock_key = "%s:%s:%s" % (
            sequence.id,
            normalized_key,
            date_range_key,
        )
        # A per-key transaction lock is necessary here to avoid two concurrent
        # creates receiving the same number before the counter row exists.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [lock_key],
        )

        counter = self.sudo().search(
            [
                ("sequence_id", "=", sequence.id),
                ("counter_key", "=", normalized_key),
                ("date_range_key", "=", date_range_key),
            ],
            limit=1,
        )
        if not counter:
            counter = self.sudo().create(
                {
                    "sequence_id": sequence.id,
                    "counter_key": normalized_key,
                    "date_range_key": date_range_key,
                    "number_next": 1,
                }
            )

        number = counter.number_next
        counter.sudo().write(
            {"number_next": number + (sequence.number_increment or 1)}
        )
        return number
