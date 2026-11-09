from . import models


def post_init_hook(env):
    """Nest add-on menus under the installed Quality app when discoverable.

    No undocumented Enterprise XML ID is referenced in XML data.
    """
    menu = env.ref('quality_rm_spec_sampling.menu_rm_qc_root', raise_if_not_found=False)
    if not menu:
        return
    checks = env['ir.actions.act_window'].sudo().search([
        ('res_model', '=', 'quality.check'),
    ])
    candidate = env['ir.ui.menu'].sudo().search([
        ('action', 'in', [f'ir.actions.act_window,{action.id}' for action in checks]),
        ('parent_id', '!=', False),
    ], limit=1)
    if candidate:
        root = candidate
        while root.parent_id:
            root = root.parent_id
        if root != menu:
            menu.sudo().write({'parent_id': root.id})
