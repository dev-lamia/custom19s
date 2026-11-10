from . import models


def post_init_hook(env):
    """Keep the addon inside the installed Quality app from first install."""
    env['ir.ui.menu']._rm_qc_place_quality_menus()


def uninstall_hook(env):
    """Restore native Quality menus before removing the custom module."""
    env['ir.ui.menu']._rm_qc_restore_quality_menus()
