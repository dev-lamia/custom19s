import base64
from pathlib import Path

from odoo import http
from odoo.http import request


_ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "src" / "img"


def _active_company():
    """Respect the active company cookie only for companies available to the user."""
    company = request.env.company.sudo()
    if not request.session.uid:
        return company
    company_ids = set(request.env.user._get_company_ids())
    cookie = request.httprequest.cookies.get("cids", "")
    first = cookie.replace(",", "-").split("-")[0]
    if first.isdecimal() and int(first) in company_ids:
        return request.env["res.company"].sudo().browse(int(first))
    return company


def _image_response(data, content_type):
    return request.make_response(
        data,
        headers=[
            ("Content-Type", content_type),
            ("Cache-Control", "private, no-store, max-age=0"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )


def _soften(color, weight=0.15):
    source = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{max(0, round(c * (1 - weight))):02X}" for c in source)


class SoftekoBrandController(http.Controller):
    @http.route(
        "/softeko_theme/favicon", type="http", auth="public",
        methods=["GET"], website=False, sitemap=False, csrf=False,
    )
    def softeko_favicon(self, **kwargs):
        company = _active_company()
        data = company.softeko_favicon
        if data:
            raw = base64.b64decode(data)
            mime = company._softeko_image_mime(raw)
            if mime:
                return _image_response(raw, mime)
        return _image_response((_ASSET_DIR / "favicon.png").read_bytes(), "image/png")

    @http.route(
        "/softeko_theme/logo", type="http", auth="user",
        methods=["GET"], website=False, sitemap=False, csrf=False,
    )
    def softeko_logo(self, **kwargs):
        company = _active_company()
        data = company.softeko_nav_logo or company.logo
        if data:
            raw = base64.b64decode(data)
            mime = company._softeko_image_mime(raw)
            if mime:
                return _image_response(raw, mime)
        return _image_response((_ASSET_DIR / "wordmark.png").read_bytes(), "image/png")

    @http.route(
        "/softeko_theme/styles.css", type="http", auth="user",
        methods=["GET"], website=False, sitemap=False, csrf=False,
    )
    def softeko_styles(self, **kwargs):
        company = _active_company()
        colors = company._softeko_colors()
        css = """:root {
  --softeko-primary: %(primary)s;
  --softeko-primary-hover: %(primary_hover)s;
  --softeko-nav-bg: %(nav)s;
  --softeko-page-bg: %(page)s;
  --softeko-logo-display: %(logo_display)s;
  --softeko-compact-space: %(compact)s;
}
""" % {
            "primary": colors["primary"],
            "primary_hover": _soften(colors["primary"]),
            "nav": colors["nav"],
            "page": colors["page"],
            "logo_display": "inline-block" if company.softeko_show_nav_logo else "none",
            "compact": "3px" if company.softeko_compact_mode else "9px",
        }
        return request.make_response(
            css,
            headers=[
                ("Content-Type", "text/css; charset=utf-8"),
                ("Cache-Control", "private, no-store, max-age=0"),
                ("X-Content-Type-Options", "nosniff"),
            ],
        )
