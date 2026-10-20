from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    # Compatibility field only. Customer filtering no longer depends on the
    # department, but keeping the field prevents older/stale database views
    # from crashing during or after the module upgrade.
    category_ids = fields.Many2many(
        comodel_name="res.partner.category",
        string="Customer Tags (Legacy)",
        help=(
            "Legacy compatibility field. Sale Order customer filtering now "
            "uses the Customer Tags configured directly on the user."
        ),
    )
