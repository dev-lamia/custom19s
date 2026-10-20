# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        session_info = super().session_info()
        session_info["flex_chatter_panel"] = {
            "chatter_position": self.env.user.fcp_chatter_position or "responsive",
        }
        return session_info
