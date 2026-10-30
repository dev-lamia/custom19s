# -*- coding: utf-8 -*-
"""Protocol-aware bulk transfers for explicitly selected users only.

The preflight validates EVERY selected user before creating any commands. A
single, dependent command sequence makes it possible to stop a large batch
safely when an individual device command fails.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZkDeviceUserBatchTransferWizard(models.TransientModel):
    _name = "zk.device.user.batch.transfer.wizard"
    _description = "Transfer Selected ZKTeco Device Users"

    device_user_ids = fields.Many2many(
        "zk.device.user", string="Selected Device Users", readonly=True,
    )
    source_device_id = fields.Many2one(
        "zk.device", string="Source Device", readonly=True,
    )
    selected_count = fields.Integer(
        string="Selected Users", compute="_compute_selected_count",
    )
    permitted_device_company_ids = fields.Many2many(
        "res.company", compute="_compute_permitted_device_company_ids",
    )
    target_device_id = fields.Many2one(
        "zk.device", string="Target Device", ondelete="restrict",
        domain="[('is_approved', '=', True), ('company_id', 'in', permitted_device_company_ids)]",
    )
    include_profile = fields.Boolean(string="Create profile if missing", default=True)
    include_access = fields.Boolean(string="Apply destination access policy", default=True)
    include_fingerprints = fields.Boolean(string="Transfer fingerprints", default=True)
    include_face = fields.Boolean(string="Transfer face templates", default=True)
    include_photo = fields.Boolean(string="Transfer profile photo", default=True)
    include_readback = fields.Boolean(string="Verify and refresh target cache", default=True)
    # API compatibility only; the form deliberately uses the explicit checks.
    transfer_mode = fields.Selection([
        ("full", "Complete transfer"), ("face_only", "Face only"),
        ("photo_only", "Photo only"),
    ], default="full", string="Legacy transfer mode")
    source_is_security_push = fields.Boolean(compute="_compute_source_is_security_push")

    @api.depends("source_device_id")
    def _compute_source_is_security_push(self):
        for wizard in self:
            wizard.source_is_security_push = (wizard.source_device_id.device_type or "").lower() == "acc"

    authorization_group_id = fields.Integer(string="Access Group ID", default=1)
    authorization_timezone_id = fields.Integer(string="Access Time Period ID", default=1)
    authorization_door_id = fields.Integer(string="Door ID", default=1)
    confirm_transfer = fields.Boolean(
        string="I checked the selected users and approved the destination access policy",
    )

    @api.depends("device_user_ids")
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.device_user_ids)

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_permitted_device_company_ids(self):
        for wizard in self:
            wizard.permitted_device_company_ids = self.env.user.company_ids

    def action_transfer(self):
        self.ensure_one()
        if not (self.env.is_superuser() or self.env.user.has_group(
            "tam_hr_zk_attendance.group_biometric_manager"
        )):
            raise UserError(_("Only Biometric Managers may transfer users."))
        users = self.device_user_ids.exists()
        if not users or len(users) > 25:
            raise UserError(_("Choose between 1 and 25 existing users."))
        if not self.source_device_id or users.mapped("device_id") != self.source_device_id:
            raise UserError(_("All selected users must belong to the same original source device."))
        if len(set(users.mapped("pin"))) != len(users):
            raise UserError(_("Source user selection contains duplicate PINs."))
        target = self.target_device_id
        if not target or target == self.source_device_id:
            raise UserError(_("Choose a different destination device."))
        for label, device in ((_("source"), self.source_device_id), (_("target"), target)):
            if (device.device_type or "").strip().lower() not in ("acc", "att", ""):
                raise UserError(_(
                    "%(role)s device %(serial)s uses unknown protocol '%(protocol)s'. "
                    "No commands were queued.", role=label,
                    serial=device.serial_number or device.display_name,
                    protocol=device.device_type,
                ))
            if not device.is_approved:
                raise UserError(_(
                    "Selected %(role)s device %(serial)s is not approved in Odoo. "
                    "Approve that device before transferring; no commands were queued.",
                    role=label, serial=device.serial_number or device.display_name,
                ))
        source_acc = (self.source_device_id.device_type or "").lower() == "acc"
        target_acc = (target.device_type or "").lower() == "acc"
        if source_acc != target_acc:
            raise UserError(_(
                "Cross-protocol biometric transfers are not verified: both source and "
                "destination must use the same protocol family (Security PUSH or Classic ADMS). "
                "No commands were queued."
            ))
        permitted = self.env.user.company_ids.ids
        if self.source_device_id.company_id.id not in permitted or target.company_id.id not in permitted:
            raise UserError(_("Access to both device companies is required."))
        if not self.confirm_transfer:
            raise UserError(_("Confirm the identities and destination access policy first."))
        operations = self._transfer_operations()
        if source_acc and operations["profile"] and not 1 <= self.authorization_group_id <= 99:
            raise UserError(_("Select a valid destination Group (1-99)."))
        if source_acc and operations["access"] and not (
            1 <= self.authorization_timezone_id <= 50
            and 1 <= self.authorization_door_id <= 16
        ):
            raise UserError(_("Select valid destination Time Period (1-50) and Door (1-16)."))
        if source_acc:
            if not target._security_push_user_inventory_status():
                raise UserError(_("Refresh destination user inventory before a bulk transfer."))
        else:
            # Unlike Security PUSH, Classic ADMS acknowledges USERINFO queries
            # separately. Do not trust stale PIN inventory for overwrite checks.
            from datetime import timedelta
            if not target.last_user_sync_at or target.last_user_sync_at < fields.Datetime.now() - timedelta(hours=24):
                raise UserError(_(
                    "Refresh the Classic ADMS destination's user inventory before "
                    "a batch transfer. This prevents overwriting a user with the same PIN."
                ))
        Command = self.env["zk.device.command"].sudo()
        if Command.search_count([
            ("device_id", "=", target.id), ("state", "in", ["pending", "sent"]),
        ]):
            raise UserError(_("Finish existing destination commands before a batch transfer."))
        users = users.sorted(key=lambda user: (user.pin or "", user.id))
        scoped_users = users.with_context(allowed_company_ids=permitted)
        scoped_target = target.with_context(allowed_company_ids=permitted)
        kwargs = dict(
            target_device=scoped_target, operations=operations,
            authorization_group_id=self.authorization_group_id,
            authorization_timezone_id=self.authorization_timezone_id,
            authorization_door_id=self.authorization_door_id,
        )
        # No commands are created during this first pass. If even one user
        # has a conflicting identity or incompatible template, none is queued.
        for user in scoped_users:
            user._queue_transfer_to_device(
                **kwargs, preflight_only=True,
            )
        before = Command.search_count([("device_id", "=", target.id)])
        previous = False
        for user in scoped_users:
            user._queue_transfer_to_device(
                **kwargs, allow_batch_pending=True,
                batch_previous_command=previous,
            )
            previous = Command.search([
                ("device_id", "=", target.id),
            ], order="id desc", limit=1)
        queued = Command.search_count([("device_id", "=", target.id)]) - before
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Selected users queued"),
                "message": _("%(users)s user(s), %(commands)s dependent command(s) queued. Monitor Command History; queueing is not proof of terminal enrollment.", users=len(users), commands=queued),
                "type": "success", "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _transfer_operations(self):
        self.ensure_one()
        if self.transfer_mode == "face_only":
            return {"profile": False, "access": False, "fingerprint": False,
                    "face": True, "photo": False, "readback": False}
        if self.transfer_mode == "photo_only":
            return {"profile": False, "access": False, "fingerprint": False,
                    "face": False, "photo": True, "readback": False}
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
