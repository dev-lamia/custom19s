# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    fcp_chatter_position = fields.Selection(
        selection=[
            ("responsive", "Responsive"),
            ("bottom", "Bottom"),
        ],
        string="Chatter Position",
        default="responsive",
        required=True,
        help=(
            "Responsive: keep standard Odoo chatter behavior. "
            "Bottom: place the chatter inside the form sheet below the form content."
        ),
    )
