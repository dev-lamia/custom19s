from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    softeko_theme_preset = fields.Selection(
        related="company_id.softeko_theme_preset", readonly=False,
        string="Softeko Color Theme",
    )
    softeko_primary_color = fields.Char(
        related="company_id.softeko_primary_color", readonly=False,
        string="Custom Primary Color",
    )
    softeko_navbar_color = fields.Char(
        related="company_id.softeko_navbar_color", readonly=False,
        string="Custom Navbar Color",
    )
    softeko_page_color = fields.Char(
        related="company_id.softeko_page_color", readonly=False,
        string="Custom Page Background",
    )
    softeko_show_sidebar = fields.Boolean(
        related="company_id.softeko_show_sidebar", readonly=False,
        string="Enable Desktop App Sidebar",
    )
    softeko_compact_mode = fields.Boolean(
        related="company_id.softeko_compact_mode", readonly=False,
        string="Compact List and Kanban Spacing",
    )
    softeko_show_nav_logo = fields.Boolean(
        related="company_id.softeko_show_nav_logo", readonly=False,
        string="Show Logo in Top Navigation",
    )
    softeko_nav_logo = fields.Image(
        related="company_id.softeko_nav_logo", readonly=False,
        string="Top Navigation Logo",
    )
    softeko_favicon = fields.Binary(
        related="company_id.softeko_favicon", readonly=False,
        string="Browser Favicon",
    )
    softeko_favicon_filename = fields.Char(
        related="company_id.softeko_favicon_filename", readonly=False,
        string="Favicon Filename",
    )
    softeko_company_logo = fields.Image(
        related="company_id.logo", readonly=False,
        string="Company / Login Logo",
    )
