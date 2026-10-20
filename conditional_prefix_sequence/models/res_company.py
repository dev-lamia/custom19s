from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sequence_prefix = fields.Char(
        string="Sequence Prefix",
        compute="_compute_sequence_prefix",
        inverse="_inverse_sequence_prefix",
        store=False,
        help=(
            "Compatibility field for older/custom company views. "
            "It mirrors Company ID (company_registry) and does not create a database column."
        ),
    )

    def _compute_sequence_prefix(self):
        for company in self:
            company.sequence_prefix = company.company_registry or ""

    def _inverse_sequence_prefix(self):
        for company in self:
            company.company_registry = company.sequence_prefix or False
