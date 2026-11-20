from odoo import models, fields, api, _


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        if result.get("is_internal_user"):
            company = self.env.company.sudo()
            result["softeko_theme"] = {
                "sidebar": bool(company.softeko_show_sidebar),
            }
        return result
