import base64
import binascii
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


COLOR_PRESETS = {
    "midnight": {"primary": "#5465D9", "nav": "#192B46", "page": "#F4F7FC"},
    "ocean": {"primary": "#1872CA", "nav": "#15334D", "page": "#F3F8FD"},
    "emerald": {"primary": "#008B7A", "nav": "#163F3B", "page": "#F1F9F7"},
    "sunset": {"primary": "#C45D48", "nav": "#49312D", "page": "#FCF7F4"},
}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ResCompany(models.Model):
    _inherit = "res.company"

    softeko_theme_preset = fields.Selection(
        selection=[
            ("midnight", "Midnight Indigo"),
            ("ocean", "Ocean Blue"),
            ("emerald", "Emerald Green"),
            ("sunset", "Warm Sunset"),
            ("custom", "Custom Colors"),
        ],
        string="Softeko Color Theme",
        default="midnight",
        required=True,
    )
    softeko_primary_color = fields.Char(
        string="Custom Primary Color", default="#5465D9",
        help="Use six-digit HEX syntax, e.g. #3456AB.",
    )
    softeko_navbar_color = fields.Char(
        string="Custom Navbar Color", default="#192B46",
    )
    softeko_page_color = fields.Char(
        string="Custom Page Background", default="#F4F7FC",
    )
    softeko_show_sidebar = fields.Boolean(
        string="Enable Desktop App Sidebar", default=True,
    )
    softeko_compact_mode = fields.Boolean(
        string="Compact List and Kanban Spacing", default=False,
    )
    softeko_show_nav_logo = fields.Boolean(
        string="Show Logo in Top Navigation", default=True,
    )
    softeko_nav_logo = fields.Image(
        string="Top Navigation Logo", attachment=True,
        max_width=700, max_height=220,
        help="Optional. If empty, the company logo is used; otherwise a Softeko fallback.",
    )
    softeko_favicon = fields.Binary(
        string="Browser Favicon", attachment=True,
        help="PNG, JPG, GIF, WebP, or ICO image. PNG 64x64 is recommended, max 2 MB.",
    )
    softeko_favicon_filename = fields.Char(string="Favicon Filename")

    @api.constrains(
        "softeko_primary_color", "softeko_navbar_color", "softeko_page_color"
    )
    def _check_softeko_colors(self):
        for company in self:
            for value in (
                company.softeko_primary_color,
                company.softeko_navbar_color,
                company.softeko_page_color,
            ):
                if value and not HEX_COLOR.fullmatch(value):
                    raise ValidationError(_("Softeko colors must use #RRGGBB format."))

    @api.constrains("softeko_favicon")
    def _check_softeko_favicon(self):
        for company in self:
            data = company.softeko_favicon
            if not data:
                continue
            # Guard before decoding to limit memory usage.
            if len(data) > 2_800_000:
                raise ValidationError(_("The favicon must be smaller than 2 MB."))
            try:
                decoded = base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                raise ValidationError(_("The favicon is not a valid image file.")) from None
            if len(decoded) > 2 * 1024 * 1024 or not self._softeko_image_mime(decoded):
                raise ValidationError(_("Upload a PNG, JPG, GIF, WebP or ICO favicon under 2 MB."))

    @api.model
    def _softeko_image_mime(self, image_bytes):
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_bytes.startswith(b"\x00\x00\x01\x00"):
            return "image/x-icon"
        if (image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP"):
            return "image/webp"
        return False

    def _softeko_colors(self):
        self.ensure_one()
        if self.softeko_theme_preset != "custom":
            return COLOR_PRESETS.get(self.softeko_theme_preset, COLOR_PRESETS["midnight"])
        return {
            "primary": self.softeko_primary_color or COLOR_PRESETS["midnight"]["primary"],
            "nav": self.softeko_navbar_color or COLOR_PRESETS["midnight"]["nav"],
            "page": self.softeko_page_color or COLOR_PRESETS["midnight"]["page"],
        }
