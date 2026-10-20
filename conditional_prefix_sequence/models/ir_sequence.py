from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

from .sequence_support import (
    STANDARD_SEQUENCE_TOKENS,
    get_dynamic_token_paths,
)


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        domain=[("transient", "=", False)],
        index=True,
        help="Model on which this conditional sequence is evaluated.",
    )
    model_name = fields.Char(
        string="Model Technical Name",
        related="model_id.model",
        readonly=True,
        store=True,
        index=True,
    )
    condition_domain = fields.Char(
        string="Condition",
        default="[]",
        help=(
            "Odoo domain evaluated on the selected model. Leave [] to use this "
            "sequence as the fallback conditional sequence for the model."
        ),
    )
    priority = fields.Integer(
        string="Priority",
        default=10,
        help="Lower values are evaluated first.",
    )
    counter_field_id = fields.Many2one(
        "ir.model.fields",
        string="Separate Counter By",
        domain="[('model_id', '=', model_id)]",
        help=(
            "Select the record field whose value should own an independent "
            "numeric counter. Leave empty to use the normal shared sequence."
        ),
    )
    counter_relation_model_id = fields.Many2one(
        "ir.model",
        string="Counter Related Model",
        compute="_compute_counter_relation_model_id",
    )
    counter_related_field_id = fields.Many2one(
        "ir.model.fields",
        string="Related Counter Field",
        domain="[('model_id', '=', counter_relation_model_id)]",
        help=(
            "Optional. If 'Separate Counter By' is a Many2one field, select a "
            "field from that related model. Example: Customer > Short Name."
        ),
    )

    @api.depends("counter_field_id", "counter_field_id.relation")
    def _compute_counter_relation_model_id(self):
        model_model = self.env["ir.model"]
        for sequence in self:
            relation = sequence.counter_field_id.relation
            sequence.counter_relation_model_id = (
                model_model._get(relation) if relation else False
            )

    @api.onchange("model_id")
    def _onchange_model_id(self):
        for sequence in self:
            sequence.condition_domain = "[]"
            sequence.counter_field_id = False
            sequence.counter_related_field_id = False

    @api.onchange("counter_field_id")
    def _onchange_counter_field_id(self):
        for sequence in self:
            sequence.counter_related_field_id = False

    def _domain_eval_context(self):
        self.ensure_one()
        return {
            "uid": self.env.uid,
            "user": self.env.user,
            "company_id": self.env.company.id,
            "context": dict(self.env.context),
        }

    def _get_condition_domain(self):
        self.ensure_one()
        domain_expression = (self.condition_domain or "[]").strip() or "[]"
        try:
            domain = safe_eval(domain_expression, self._domain_eval_context())
        except Exception as exc:
            raise ValidationError(
                _(
                    "Invalid condition domain on sequence '%(sequence)s': %(error)s",
                    sequence=self.display_name,
                    error=exc,
                )
            ) from exc

        if not isinstance(domain, (list, tuple)):
            raise ValidationError(
                _(
                    "The condition on sequence '%s' must be a valid Odoo domain.",
                    self.display_name,
                )
            )
        return list(domain)

    @api.constrains("condition_domain", "model_id")
    def _check_condition_domain(self):
        for sequence in self:
            if not sequence.model_id:
                continue
            domain = sequence._get_condition_domain()
            try:
                self.env[sequence.model_id.model]._search(domain, limit=1)
            except Exception as exc:
                raise ValidationError(
                    _(
                        "The condition domain is not valid for model "
                        "'%(model)s': %(error)s",
                        model=sequence.model_id.display_name,
                        error=exc,
                    )
                ) from exc

    def _normalized_condition_domain(self):
        self.ensure_one()
        return repr(expression.normalize_domain(self._get_condition_domain()))

    @api.constrains("model_id", "condition_domain", "company_id", "active")
    def _check_duplicate_model_condition(self):
        for sequence in self:
            if not sequence.active or not sequence.model_id:
                continue

            company_domain = (
                [("company_id", "=", sequence.company_id.id)]
                if sequence.company_id
                else [("company_id", "=", False)]
            )
            candidates = self.search(
                [
                    ("id", "!=", sequence.id),
                    ("active", "=", True),
                    ("model_id", "=", sequence.model_id.id),
                    *company_domain,
                ]
            )
            normalized = sequence._normalized_condition_domain()
            duplicate = candidates.filtered(
                lambda candidate: candidate._normalized_condition_domain() == normalized
            )[:1]
            if duplicate:
                company_name = sequence.company_id.display_name or _("All Companies")
                raise ValidationError(
                    _(
                        "A sequence already exists for this Model and Condition.\n\n"
                        "Existing Sequence: %(existing)s\n"
                        "Model: %(model)s\n"
                        "Company: %(company)s\n\n"
                        "Please modify the existing sequence instead of creating "
                        "a duplicate.",
                        existing=duplicate.display_name,
                        model=sequence.model_id.display_name,
                        company=company_name,
                    )
                )

    def _condition_field_names(self):
        self.ensure_one()
        names = set()
        for token in self._get_condition_domain():
            if isinstance(token, (list, tuple)) and len(token) >= 3:
                field_name = token[0]
                if isinstance(field_name, str):
                    names.add(field_name.split(".", 1)[0])
        return names

    def _matches_record_conditions(self, record):
        self.ensure_one()
        if not self.model_id or self.model_id.model != record._name:
            return False
        domain = self._get_condition_domain()
        return True if not domain else bool(record.filtered_domain(domain))

    @api.model
    def _get_model_sequences(self, model_name, company):
        company_id = company.id if company else self.env.company.id
        return self.search(
            [
                ("active", "=", True),
                ("model_name", "=", model_name),
                ("company_id", "in", [False, company_id]),
            ],
            order="priority asc, id asc",
        )

    @api.model
    def _get_for_record(self, record, allow_fallback=True):
        if not record or len(record) != 1:
            raise ValidationError(_("A single record is required to resolve a sequence."))

        company = (
            record.company_id
            if "company_id" in record._fields and record.company_id
            else record.env.company
        )
        sequences = self._get_model_sequences(record._name, company)
        company_sequences = sequences.filtered(
            lambda sequence: sequence.company_id == company
        )
        global_sequences = sequences.filtered(lambda sequence: not sequence.company_id)

        for scoped_sequences in (company_sequences, global_sequences):
            fallback = self.browse()
            for sequence in scoped_sequences:
                if not sequence._get_condition_domain():
                    fallback = fallback or sequence
                    continue
                if sequence._matches_record_conditions(record):
                    return sequence
            if fallback and allow_fallback:
                return fallback
        return self.browse()

    @api.model
    def _get_watched_fields(self, model_name, company):
        fields_to_watch = set()
        for sequence in self._get_model_sequences(model_name, company):
            fields_to_watch.update(sequence._condition_field_names())
            fields_to_watch.update(
                path.split(".", 1)[0]
                for path in get_dynamic_token_paths(sequence)
            )
            counter_path = sequence._get_counter_field_path()
            if counter_path:
                fields_to_watch.add(counter_path.split(".", 1)[0])
        return fields_to_watch


    def _get_counter_field_path(self):
        self.ensure_one()
        if not self.counter_field_id:
            return False
        path = self.counter_field_id.name
        if self.counter_related_field_id:
            path = "%s.%s" % (path, self.counter_related_field_id.name)
        return path

    @api.constrains(
        "model_id",
        "counter_field_id",
        "counter_related_field_id",
    )
    def _check_counter_fields(self):
        for sequence in self:
            if not sequence.counter_field_id:
                if sequence.counter_related_field_id:
                    raise ValidationError(
                        _("Select 'Separate Counter By' before a related field.")
                    )
                continue
            if sequence.counter_field_id.model_id != sequence.model_id:
                raise ValidationError(
                    _("The counter field must belong to the selected Model.")
                )
            if sequence.counter_related_field_id:
                if sequence.counter_field_id.ttype != "many2one":
                    raise ValidationError(
                        _("A Related Counter Field requires a Many2one counter field.")
                    )
                relation_model = sequence.counter_relation_model_id
                if sequence.counter_related_field_id.model_id != relation_model:
                    raise ValidationError(
                        _("The related counter field belongs to the wrong model.")
                    )

    def _validate_dynamic_field_path(self, field_path):
        self.ensure_one()
        if not self.model_id:
            raise ValidationError(
                _("Select a Model before using record field tokens in Prefix/Suffix.")
            )

        model = self.env[self.model_id.model]
        current_model = model
        parts = field_path.split(".")
        for index, part in enumerate(parts):
            field = current_model._fields.get(part)
            if not field:
                raise ValidationError(
                    _(
                        "Invalid record token '%%(%(token)s)s' for model '%(model)s'. "
                        "Field '%(field)s' does not exist.",
                        token=field_path,
                        model=self.model_id.display_name,
                        field=part,
                    )
                )
            if index < len(parts) - 1:
                if field.type != "many2one":
                    raise ValidationError(
                        _(
                            "Invalid record token '%%(%(token)s)s'. Field '%(field)s' "
                            "must be a Many2one field for a dotted path.",
                            token=field_path,
                            field=part,
                        )
                    )
                current_model = self.env[field.comodel_name]

    @api.constrains("prefix", "suffix", "model_id")
    def _check_dynamic_record_tokens(self):
        for sequence in self:
            for field_path in get_dynamic_token_paths(sequence):
                sequence._validate_dynamic_field_path(field_path)

    def _get_prefix_suffix(self, date=None, date_range=None):
        """Odoo 19 prefix/suffix interpolation plus dynamic record values."""
        dynamic_values = self.env.context.get("conditional_sequence_values")
        if not dynamic_values:
            return super()._get_prefix_suffix(date=date, date_range=date_range)

        from datetime import datetime

        def _interpolate(template, values):
            return (template % values) if template else ""

        now = range_date = effective_date = datetime.now(self.env.tz)
        if date or self.env.context.get("ir_sequence_date"):
            effective_date = fields.Datetime.from_string(
                date or self.env.context.get("ir_sequence_date")
            )
        if date_range or self.env.context.get("ir_sequence_date_range"):
            range_date = fields.Datetime.from_string(
                date_range or self.env.context.get("ir_sequence_date_range")
            )

        formats = {
            "year": "%Y",
            "month": "%m",
            "day": "%d",
            "y": "%y",
            "doy": "%j",
            "woy": "%W",
            "weekday": "%w",
            "h24": "%H",
            "h12": "%I",
            "min": "%M",
            "sec": "%S",
            "isoyear": "%G",
            "isoy": "%g",
            "isoweek": "%V",
        }
        values = {}
        for key, date_format in formats.items():
            values[key] = effective_date.strftime(date_format)
            values["range_" + key] = range_date.strftime(date_format)
            values["current_" + key] = now.strftime(date_format)
        values.update(dynamic_values)

        self.ensure_one()
        try:
            return (
                _interpolate(self.prefix, values),
                _interpolate(self.suffix, values),
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise UserError(
                _("Invalid prefix or suffix for sequence “%s”", self.name)
            ) from exc

    @api.model
    def next_by_record(self, record, sequence_date=None):
        sequence = self._get_for_record(record)
        if not sequence:
            return False
        from .sequence_support import get_next_sequence_value

        return get_next_sequence_value(
            sequence, record, sequence_date=sequence_date
        )

    def next_by_id(self, sequence_date=None):
        """Draw the next value, using a per-customer counter when configured."""
        self.ensure_one()
        counter_key = self.env.context.get("conditional_sequence_counter_key")
        if not counter_key:
            return super().next_by_id(sequence_date=sequence_date)

        self.browse().check_access("read")
        number = self.env["conditional.sequence.counter"]._next_number(
            self,
            counter_key,
            sequence_date=sequence_date,
        )
        if number is False:
            return super().next_by_id(sequence_date=sequence_date)

        context_values = {}
        if sequence_date:
            context_values["ir_sequence_date"] = sequence_date
        if self.use_date_range:
            current_sequence = self._get_current_sequence(
                sequence_date=sequence_date
            )
            if current_sequence._name == "ir.sequence.date_range":
                context_values["ir_sequence_date_range"] = current_sequence.date_from

        return self.with_context(**context_values).get_next_char(number)
