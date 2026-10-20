from odoo import fields, models


class ProjectApprovalNotice(models.TransientModel):
    _name = "project.approval.notice"
    _description = "Project Approval Notice"

    title = fields.Char(
        string="Title",
        readonly=True,
    )

    message = fields.Text(
        string="Message",
        readonly=True,
    )

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}