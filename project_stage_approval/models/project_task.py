from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    workflow_initiator_id = fields.Many2one(
        "res.users",
        string="Workflow Initiator",
        readonly=True,
        copy=False,
        tracking=True,
    )

    approved_approver_ids = fields.Many2many(
        "res.users",
        "task_stage_approved_rel",
        "task_id",
        "user_id",
        string="Approved By",
        readonly=True,
        copy=False,
    )

    can_next = fields.Boolean(
        compute="_compute_workflow_flags",
    )
    has_next_stage = fields.Boolean(
        compute="_compute_workflow_flags",
    )

    can_approve = fields.Boolean(
        compute="_compute_workflow_flags",
    )

    can_review = fields.Boolean(
        compute="_compute_workflow_flags",
    )

    approval_required = fields.Boolean(
        compute="_compute_workflow_flags",
    )

    approval_complete = fields.Boolean(
        compute="_compute_workflow_flags",
    )

    @api.depends(
        "project_id",
        "stage_id",
        "stage_id.approver_ids",
        "approved_approver_ids",
    )
    @api.depends_context("uid")
    def _compute_workflow_flags(self):
        user = self.env.user

        for task in self:
            approvers = task.stage_id.approver_ids
            approved = task.approved_approver_ids

            task.has_next_stage = bool(
                task._get_adjacent_stage(1)
            )
            task.approval_required = bool(approvers)
            task.approval_complete = bool(
                approvers and approvers <= approved
            )
            task.can_approve = (
                user in approvers
                and user not in approved
            )
            task.can_review = (
                user in approvers
                and bool(task._get_adjacent_stage(-1))
            )


    # @api.depends(
    #     "project_id",
    #     "stage_id",
    #     "stage_id.approver_ids",
    #     "approved_approver_ids",
    # )
    # @api.depends_context("uid")
    # def _compute_workflow_flags(self):
    #     user = self.env.user

    #     for task in self:
    #         approvers = task.stage_id.approver_ids
    #         approved = task.approved_approver_ids
    #         is_approver = user in approvers
    #         has_approved = user in approved
    #         pending_approvers = approvers - approved

    #         task.has_next_stage = bool(task._get_adjacent_stage(1))
    #         task.approval_required = bool(approvers)
    #         task.approval_complete = bool(
    #             approvers and not pending_approvers
    #         )

    #         task.can_approve = (
    #             is_approver
    #             and not has_approved
    #         )

    #         task.can_review = (
    #             is_approver
    #             and not has_approved
    #             and bool(task._get_adjacent_stage(-1))
    #         )

    #         task.can_next = not (
    #             is_approver and has_approved
    #         )





    def _get_adjacent_stage(self, direction):
        self.ensure_one()

        if not self.project_id or not self.stage_id:
            return self.env["project.task.type"]

        stages = self.env["project.task.type"].search(
            [
                ("project_ids", "in", self.project_id.id),
                ("active", "=", True),
            ],
            order="sequence, id",
        )

        if self.stage_id not in stages:
            return self.env["project.task.type"]

        current_index = stages.ids.index(self.stage_id.id)
        target_index = current_index + direction

        if target_index < 0 or target_index >= len(stages):
            return self.env["project.task.type"]

        return stages[target_index]

    def _approval_summary(self, stage):
        return _("Stage Approval Needed: %s", stage.name)

    def _clear_stage_approval_activities(self):
        self.ensure_one()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("summary", "=", self._approval_summary(self.stage_id)),
        ])

        if activities:
            activities.unlink()

    def _schedule_stage_approval_activities(self):
        activity_type = "mail.mail_activity_data_todo"

        for task in self:
            approvers = (
                task.stage_id.approver_ids
                - task.approved_approver_ids
            )

            if not approvers:
                continue

            for approver in approvers:
                task.activity_schedule(
                    activity_type,
                    date_deadline=fields.Date.context_today(task),
                    summary=task._approval_summary(task.stage_id),
                    note=_(
                        "Please review task %(task)s in stage "
                        "%(stage)s. Use the Approve or Review "
                        "button on the task.",
                        task=task.display_name,
                        stage=task.stage_id.name,
                    ),
                    user_id=approver.id,
                )

    def _complete_current_approval_activity(self, feedback):
        self.ensure_one()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("user_id", "=", self.env.user.id),
            ("summary", "=", self._approval_summary(self.stage_id)),
        ])

        if activities:
            activities.action_feedback(feedback=feedback)

    def _notify_workflow_initiator(self, summary, note):
        self.ensure_one()

        if not self.workflow_initiator_id:
            return

        self.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=fields.Date.context_today(self),
            summary=summary,
            note=note,
            user_id=self.workflow_initiator_id.id,
        )


    def _show_approval_notice(self, title, message):
        self.ensure_one()

        notice = self.env["project.approval.notice"].create({
            "title": title,
            "message": message,
        })

        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "project.approval.notice",
            "res_id": notice.id,
            "view_mode": "form",
            "target": "new",
        }


    def action_next_stage(self):
        self.ensure_one()

        current_stage = self.stage_id
        approvers = current_stage.approver_ids

        if approvers:
            pending_approvers = approvers - self.approved_approver_ids

            if pending_approvers:
                names = ", ".join(pending_approvers.mapped("name"))

                return self._show_approval_notice(
                    _("Approval Needed"),
                    _(
                        'Approval needed for "%(task)s". '
                        "You are not an assigned approver.\n\n"
                        "Waiting for: %(approvers)s",
                        task=self.display_name,
                        approvers=names,
                    ),
                )

        next_stage = self._get_adjacent_stage(1)

        if not next_stage:
            return self._show_approval_notice(
                _("No Next Stage"),
                _("There is no next stage for this task."),
            )

        self.write({
            "workflow_initiator_id": self.env.user.id,
            "stage_id": next_stage.id,
            "approved_approver_ids": [fields.Command.clear()],
        })

        if next_stage.approver_ids:
            self._schedule_stage_approval_activities()

            names = ", ".join(
                next_stage.approver_ids.mapped("name")
            )

            return self._show_approval_notice(
                _("Approval Required"),
                _(
                    'Approval request created for "%(task)s". '
                    "Waiting for: %(approvers)s",
                    task=self.display_name,
                    approvers=names,
                ),
            )

        return True


    def action_approve_stage(self):
        self.ensure_one()

        user = self.env.user
        approvers = self.stage_id.approver_ids

        if user not in approvers:
            raise UserError(
                _("You are not an approver for the current stage.")
            )

        if user in self.approved_approver_ids:
            raise UserError(
                _("You have already approved this stage.")
            )

        stage_name = self.stage_id.name
        approver_name = user.name

        self.write({
            "approved_approver_ids": [
                fields.Command.link(user.id)
            ],
        })

        self._complete_current_approval_activity(
            _("Approved by %s.", approver_name)
        )

        self._notify_workflow_initiator(
            _("Stage Approved: %s", stage_name),
            _(
                "%(approver)s approved stage %(stage)s "
                "for task %(task)s.",
                approver=approver_name,
                stage=stage_name,
                task=self.display_name,
            ),
        )


        return True

    def action_review_stage(self):
        self.ensure_one()

        user = self.env.user

        if user not in self.stage_id.approver_ids:
            raise UserError(
                _("You are not an approver for the current stage.")
            )

        previous_stage = self._get_adjacent_stage(-1)

        if not previous_stage:
            raise UserError(
                _("There is no previous stage for this task.")
            )

        current_stage_name = self.stage_id.name
        approver_name = user.name
        initiator = self.workflow_initiator_id

        self._complete_current_approval_activity(
            _("Review requested by %s.", approver_name)
        )

        self.write({
            "stage_id": previous_stage.id,
            "approved_approver_ids": [fields.Command.clear()],
        })

        self._schedule_stage_approval_activities()

        if initiator:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=fields.Date.context_today(self),
                summary=_(
                    "Review Requested: %s",
                    current_stage_name,
                ),
                note=_(
                    "%(approver)s requested review of stage "
                    "%(stage)s for task %(task)s. The task has "
                    "been returned to %(previous)s.",
                    approver=approver_name,
                    stage=current_stage_name,
                    task=self.display_name,
                    previous=previous_stage.name,
                ),
                user_id=initiator.id,
            )

        return True