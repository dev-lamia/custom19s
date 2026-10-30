# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZkDeviceUserTransferWizard(models.TransientModel):
    _name = "zk.device.user.transfer.wizard"
    _description = "Transfer ZKTeco Device User"

    device_user_id = fields.Many2one("zk.device.user", required=True, readonly=True, ondelete="cascade")
    source_device_id = fields.Many2one(related="device_user_id.device_id", string="Source Device", readonly=True)
    source_pin = fields.Char(related="device_user_id.pin", string="Device PIN", readonly=True)
    source_name = fields.Char(related="device_user_id.name", string="Name on Device", readonly=True)
    employee_id = fields.Many2one(related="device_user_id.employee_id", string="Mapped Employee", readonly=True)
    source_company_id = fields.Many2one(related="source_device_id.company_id", readonly=True)
    permitted_device_company_ids = fields.Many2many(
        "res.company", compute="_compute_permitted_device_company_ids",
        compute_sudo=False, string="Permitted Device Companies",
    )

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_permitted_device_company_ids(self):
        # Company selector is scoped to companies assigned to the operator,
        # including secondary companies not active in the company switcher.
        for wizard in self:
            wizard.permitted_device_company_ids = self.env.user.company_ids
    include_profile = fields.Boolean(string="Create profile if missing", default=True)
    include_access = fields.Boolean(
        string="Apply destination access policy", default=True,
        help="Security PUSH only. Uses the Group, Time Period and Door selected below.",
    )
    include_fingerprints = fields.Boolean(string="Transfer fingerprints", default=True)
    include_face = fields.Boolean(string="Transfer face templates", default=True)
    include_photo = fields.Boolean(string="Transfer profile photo", default=True)
    include_readback = fields.Boolean(
        string="Verify and refresh target cache", default=True,
        help="Queues a target readback after transfer so the new user and selected templates are reflected in Odoo.",
    )
    # Compatibility for server/API callers from earlier releases. This field is
    # intentionally absent from the UI; managers now use the explicit checks.
    transfer_mode = fields.Selection([
        ("full", "Complete transfer"), ("profile_only", "Profile only"),
        ("templates_only", "Templates only"), ("authorize_only", "Access only"),
        ("face_only", "Face only"), ("photo_only", "Photo only"),
    ], default="full", string="Legacy transfer mode")
    source_is_security_push = fields.Boolean(compute="_compute_source_is_security_push")
    authorization_group_id = fields.Integer(
        string="Target Access Group ID", default=1,
        help="Group ID configured for this user's approved destination access policy (1–99). Do not assume source Group 1 is equivalent.",
    )
    authorization_timezone_id = fields.Integer(
        string="Target Access Time Period ID", default=1,
        help="Enter the time-period ID configured on the DESTINATION terminal. ID 1 can mean 24-hour access; obtain approved policy first.",
    )
    authorization_door_id = fields.Integer(
        string="Target Door ID", default=1,
        help="Enter the door ID that the user should access on the destination terminal (often 1).",
    )

    @api.depends("source_device_id")
    def _compute_source_is_security_push(self):
        for wizard in self:
            wizard.source_is_security_push = (wizard.source_device_id.device_type or "").lower() == "acc"
    confirm_transfer = fields.Boolean(
        string="I verified the user, target device, and the selected destination door/time-period policy",
    )
    template_count = fields.Integer(string="Cached Templates", compute="_compute_template_count", readonly=True)
    source_face_count = fields.Integer(string="Cached Source Face Templates", compute="_compute_face_counts", readonly=True)
    target_face_count = fields.Integer(string="Cached Target Face Templates", compute="_compute_face_counts", readonly=True)
    source_has_photo = fields.Boolean(string="Source Has Profile Picture", compute="_compute_photo_status", readonly=True)
    target_has_photo = fields.Boolean(string="Cached Target Has Picture", compute="_compute_photo_status", readonly=True)

    @api.depends("device_user_id", "target_device_id")
    def _compute_face_counts(self):
        biometric = self.env["zk.device.biometric.template"].sudo()
        for wizard in self:
            wizard.source_face_count = 0
            wizard.target_face_count = 0
            if not wizard.device_user_id or not wizard.source_pin:
                continue
            wizard.source_face_count = biometric.search_count([
                ("device_id", "=", wizard.source_device_id.id),
                ("pin", "=", wizard.source_pin), ("biometric_type", "=", "face"),
            ])
            if wizard.target_device_id and wizard.target_device_id.company_id.id in self.env.user.company_ids.ids:
                wizard.target_face_count = biometric.search_count([
                    ("device_id", "=", wizard.target_device_id.id),
                    ("pin", "=", wizard.source_pin), ("biometric_type", "=", "face"),
                ])

    @api.depends("device_user_id", "device_user_id.image_1920", "target_device_id")
    def _compute_photo_status(self):
        target_user_model = self.env["zk.device.user"].sudo()
        for wizard in self:
            wizard.source_has_photo = bool(wizard.device_user_id.image_1920) if wizard.device_user_id else False
            wizard.target_has_photo = False
            if wizard.target_device_id and wizard.source_pin and wizard.target_device_id.company_id.id in self.env.user.company_ids.ids:
                target_user = target_user_model.search([
                    ("device_id", "=", wizard.target_device_id.id),
                    ("pin", "=", wizard.source_pin),
                ], limit=1)
                wizard.target_has_photo = bool(target_user.image_1920)

    # The action pre-creates the transient with its source. The operator chooses
    # the target afterwards, so database-level required=True would prevent
    # creating the wizard at all. Enforce required in the form and action.
    target_device_id = fields.Many2one("zk.device", string="Target Device", domain="[('is_approved', '=', True), ('company_id', 'in', permitted_device_company_ids)]", ondelete="restrict")
    # Not a direct related field: a related lookup runs under the currently
    # active company and can fail for another *permitted* target company.
    target_last_user_sync_at = fields.Datetime(
        compute="_compute_target_last_user_sync_at",
        string="Target Users Last Refreshed", readonly=True,
    )
    target_cache_status = fields.Char(compute="_compute_target_cache_status", readonly=True)

    @api.depends("device_user_id")
    def _compute_template_count(self):
        Fingerprint = self.env["zk.device.fingerprint"].sudo()
        Biometric = self.env["zk.device.biometric.template"].sudo()
        for wizard in self:
            if not wizard.device_user_id:
                wizard.template_count = 0
            elif (wizard.source_device_id.device_type or "").lower() == "acc":
                wizard.template_count = Biometric.search_count([
                    ("device_id", "=", wizard.source_device_id.id),
                    ("pin", "=", wizard.source_pin),
                ])
            else:
                wizard.template_count = Fingerprint.search_count([
                    ("device_id", "=", wizard.source_device_id.id),
                    ("pin", "=", wizard.source_pin),
                ]) + Biometric.search_count([
                    ("device_id", "=", wizard.source_device_id.id),
                    ("pin", "=", wizard.source_pin),
                    ("biometric_type", "=", "face"),
                ])

    @api.depends("target_device_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_target_last_user_sync_at(self):
        permitted = self.env.user.company_ids.ids
        for wizard in self:
            target = wizard.target_device_id.with_context(allowed_company_ids=permitted)
            wizard.target_last_user_sync_at = (
                target.last_user_sync_at
                if target and target.company_id.id in permitted else False
            )

    @api.depends("target_device_id", "target_last_user_sync_at")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_target_cache_status(self):
        permitted = self.env.user.company_ids.ids
        for wizard in self:
            target = wizard.target_device_id.with_context(allowed_company_ids=permitted)
            if not target:
                wizard.target_cache_status = "Choose an approved target device."
            elif target.company_id.id not in permitted:
                wizard.target_cache_status = "You do not have access to this target company."
            elif (target.device_type or "").lower() != "acc":
                from datetime import timedelta
                if target.last_user_sync_at and target.last_user_sync_at >= fields.Datetime.now() - timedelta(hours=24):
                    wizard.target_cache_status = "Classic ADMS user inventory refreshed in the past 24 hours."
                else:
                    wizard.target_cache_status = "Refresh Classic ADMS target users (USERINFO) before transfer."
            else:
                status = target._security_push_user_inventory_status()
                if status == "empty":
                    wizard.target_cache_status = "Verified empty inventory (successful user query returned 0). Ready for a first profile transfer."
                elif status == "records":
                    wizard.target_cache_status = "Target user inventory verified within the past 24 hours."
                else:
                    wizard.target_cache_status = "Run Pull Users and Templates on the target first. A completed result of 0 users is valid."


    def action_transfer(self):
        self.ensure_one()
        if not self.device_user_id or not self.device_user_id.exists():
            raise UserError(_("The source device user is no longer available. Close and reopen the transfer wizard."))
        if not self.target_device_id:
            raise UserError(_("Choose an approved target device before transferring."))
        if self.target_device_id == self.source_device_id:
            raise UserError(_("Select another approved device. Updating the same device is a different action."))
        if not self.confirm_transfer:
            raise UserError(_("Confirm that you verified the user identity and the target device."))
        # Expand only to companies assigned to this user. Odoo's default
        # allowed_company_ids normally includes only the actively selected
        # company and would hide/reject other authorized destinations.
        permitted = self.env.user.company_ids.ids
        source = self.device_user_id.with_context(allowed_company_ids=permitted)
        target = self.target_device_id.with_context(allowed_company_ids=permitted)
        is_security = (source.device_id.device_type or "").lower() == "acc"
        operations = self._transfer_operations()
        if is_security and (operations["profile"] or operations["access"]):
            # A single explicit confirmation covers both identity and the
            # potentially permissive destination access policy.
            if not (1 <= self.authorization_timezone_id <= 50 and 1 <= self.authorization_door_id <= 16):
                raise UserError(_("Enter a valid destination time-period ID (1–50) and door ID (1–16)."))
            if operations["profile"] and not 1 <= self.authorization_group_id <= 99:
                raise UserError(_("Enter a valid destination access group (1–99)."))
        result = source._queue_transfer_to_device(
            target, operations=operations,
            authorization_timezone_id=self.authorization_timezone_id if is_security else 0,
            authorization_door_id=self.authorization_door_id if is_security else 0,
            authorization_group_id=self.authorization_group_id if is_security else 0,
        )
        # The model method is also callable outside the transient dialog.
        # Only the wizard needs the toast to close its own modal afterwards.
        if result.get("type") == "ir.actions.client" and result.get("tag") == "display_notification":
            result["params"]["next"] = {"type": "ir.actions.act_window_close"}
        return result

    def _transfer_operations(self):
        self.ensure_one()
        legacy = self.transfer_mode or "full"
        if legacy != "full":
            selections = {
                "profile_only": {"profile", "access", "readback"},
                "templates_only": {"fingerprint", "face"},
                "authorize_only": {"access"}, "face_only": {"face"},
                "photo_only": {"photo"},
            }
            return {key: key in selections[legacy] for key in (
                "profile", "access", "fingerprint", "face", "photo", "readback",
            )}
        operations = {
            "profile": self.include_profile,
            "access": self.include_access,
            "fingerprint": self.include_fingerprints,
            "face": self.include_face,
            "photo": self.include_photo,
            "readback": self.include_readback,
        }
        if not any(operations.values()):
            raise UserError(_("Select at least one transfer operation."))
        return operations
