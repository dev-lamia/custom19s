from odoo import api, models

from .sequence_support import prepare_conditional_values, regenerate_after_condition_change


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    @api.model_create_multi
    def create(self, vals_list):
        prepare_conditional_values(self, vals_list)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        regenerate_after_condition_change(self, vals)
        return result
