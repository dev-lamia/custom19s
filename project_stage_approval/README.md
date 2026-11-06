# Project Stage Approval (Odoo 19)

A custom Project Task approval workflow. Stage approvers review a task before it can proceed. A **Return to Stage** field on each task stage determines where the task goes when an approver clicks **Review** (requests changes/rejects).

## Requirements

- Odoo 19
- `project` (installed automatically as a dependency)
- Standard Odoo Project Manager permissions to configure stage approvers and return destinations

## Installation / upgrade

Copy the `project_stage_approval` directory to your custom addons path, restart Odoo, update the Apps List, and install or upgrade **Project Stage Approval**. From an Odoo.sh checkout you can commit the updated directory and upgrade the module in Apps.

## Configuration

1. Open **Project → Configuration → Task Stages** (the menu name can vary by configuration).
2. Open a stage and choose **Approvers**.
3. Use the adjacent **Return to Stage** dropdown to choose the stage that should receive a task if its approval is rejected/reviewed.
4. Save the stage.

The return destination must be an active stage available to the task's project and cannot be the same stage. Leave it blank for the original behavior: return to the immediately preceding stage. A stage shared by multiple projects must have a return destination available in every project where it will be used, or users will receive a validation message when requesting review.

## Task buttons

- **Next**: advances the task when the current stage's assigned approvers have all approved, resets approvals, and schedules activities for approvers in the destination stage.
- **Approve**: an assigned approver approves the current stage and completes their assigned approval activity. The workflow initiator receives an activity.
- **Review**: an assigned approver requests rework/rejects the current stage; the task moves to **Return to Stage** (or the preceding stage when not configured), previous-stage approval flags are cleared, outstanding activities for the rejected stage are removed, new stage approvers are notified, and the workflow initiator receives a review activity.

The workflow continues to use the existing transient approval notice screen.

## Files

- `models/project_task_type.py`: stage approvers and configurable return stage.
- `models/project_task.py`: advancement, approval, rejection/review, and activities.
- `views/project_task_type_views.xml`: stage configuration fields.
- `views/project_task_views.xml`: workflow buttons and task information.
- `wizard/approval_notice.py`, `views/approval_notice_views.xml`: message modal.
- `workflow.md`: step-by-step workflow and examples.

## Scope and limitations

- The **Review** button is the existing rejection/rework action; it has not been renamed.
- Only users assigned as stage approvers can approve or review the stage.
- Standard task stage navigation rules and permissions still apply; this module does not override all possible drag-and-drop or external writes to task stages.
- No historical tasks or approvals are migrated by this change.
- Before deploying to production, test a task with multiple approvers and a custom return stage in a staging database.

## Git commit

`[Feat]: Configure rejection return stages for project task approvals`
