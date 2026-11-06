from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    return_stage_id = fields.Many2one(
        "project.task.type",
        string="Return to Stage",
        ondelete="set null",
        help=(
            "Stage to return to when an approver clicks Review. "
            "If empty, the task returns to the preceding stage."
        ),
    )

    @api.constrains("return_stage_id")
    def _check_return_stage(self):
        for stage in self:
            if stage.return_stage_id == stage:
                raise ValidationError(
                    _("Return to Stage cannot be the same as the current stage.")
                )
