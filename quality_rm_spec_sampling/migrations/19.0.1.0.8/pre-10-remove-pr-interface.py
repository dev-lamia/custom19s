"""Remove obsolete PR navigation/access records from previously installed databases.

The PR business models are no longer included in the updated module.
Database administrators must back up legacy PR records before this upgrade.
"""

from odoo import api, SUPERUSER_ID


# Odoo's migration contract uses a database cursor (not a legacy model API).
def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    xmlids = [
        # Remove navigation first, then its action and views.
        'menu_rm_qc_pr',
        'action_rm_qc_pr',
        'view_rm_qc_pr_form',
        'view_rm_qc_pr_list',
        # Rules and access grants bound to legacy PR models.
        'rule_pr_company',
        'access_qc_pr_inspector',
        'access_qc_pr_controller',
        'access_qc_pr_approver',
        'access_qc_prline_inspector',
        'access_qc_prline_controller',
        'access_qc_pr_purchase',
        'access_qc_prline_purchase',
        'access_rm_qc_internal_full_purchase_request',
        'access_rm_qc_internal_full_purchase_request_line',
        'group_rm_qc_pr_approver',
        'seq_rm_qc_pr',
    ]
    for xmlid in xmlids:
        rec = env.ref('quality_rm_spec_sampling.%s' % xmlid,
                      raise_if_not_found=False)
        if rec and rec.exists():
            rec.sudo().unlink()
