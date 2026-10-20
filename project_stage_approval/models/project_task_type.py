from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    approver_ids = fields.Many2many(
        "res.users",
        relation="task_stage_appr_rel",
        column1="stage_id",
        column2="user_id",
        string="Approvers",
        domain=[
            ("share", "=", False),
            ("active", "=", True),
        ],
        help="Users who must review tasks entering this stage.",
    )