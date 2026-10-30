# -*- coding: utf-8 -*-
"""Classic/legacy ADMS batch transfer regression tests for Odoo 19."""
import base64
import io

from PIL import Image
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestClassicBatchTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        common = {"is_approved": True, "company_id": cls.env.company.id}
        cls.source = cls.env["zk.device"].create({
            **common, "name": "Classic source", "serial_number": "CLASSIC-SOURCE-58",
            "device_type": "att",
        })
        cls.target = cls.env["zk.device"].create({
            **common, "name": "Classic target", "serial_number": "CLASSIC-TARGET-58",
            "device_type": "att", "last_user_sync_at": fields.Datetime.now(),
        })
        cls.users = cls.env["zk.device.user"].create([
            {"device_id": cls.source.id, "pin": "5801", "name": "Classic One"},
            {"device_id": cls.source.id, "pin": "5802", "name": "Classic Two"},
        ])

    def _wizard(self, mode="full"):
        return self.env["zk.device.user.batch.transfer.wizard"].create({
            "device_user_ids": [(6, 0, self.users.ids)],
            "source_device_id": self.source.id,
            "target_device_id": self.target.id,
            "transfer_mode": mode, "confirm_transfer": True,
        })

    def _commands(self):
        return self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id")

    @staticmethod
    def _jpeg():
        stream = io.BytesIO()
        Image.new("RGB", (48, 48), "white").save(stream, format="JPEG")
        return base64.b64encode(stream.getvalue())

    def test_batch_classic_chains_verified_users_without_security_commands(self):
        opened = self.users.action_open_batch_transfer_wizard()
        self.assertEqual(opened["res_model"], "zk.device.user.batch.transfer.wizard")
        self._wizard().action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 4)
        self.assertTrue(commands[0].command.startswith("DATA USER PIN=5801"))
        self.assertEqual(commands[1].command, "DATA QUERY USERINFO PIN=5801")
        self.assertEqual(commands[2].command.split(" ", 2)[0], "DATA")
        self.assertTrue(all("userauthorize" not in cmd.command for cmd in commands))
        for current, previous in zip(commands[1:], commands[:-1]):
            self.assertEqual(current.depends_on_id, previous)

    def test_legacy_handshake_without_devicetype_uses_classic_adapter(self):
        self.source.write({"device_type": False})
        self._wizard().action_transfer()
        self.assertEqual(len(self._commands()), 4)

    def test_mixed_protocol_rejected_without_side_effects(self):
        self.target.write({"device_type": "acc"})
        with self.assertRaisesRegex(UserError, "Cross-protocol"):
            self._wizard().action_transfer()
        self.assertFalse(self._commands())

    def test_second_user_collision_blocks_entire_batch(self):
        self.env["zk.device.user"].create({
            "device_id": self.target.id, "pin": "5802",
            "name": "Different Human",
        })
        with self.assertRaises(UserError):
            self._wizard().action_transfer()
        self.assertFalse(self._commands())

    def test_photo_repair_is_separate_and_firmware_dependent(self):
        photo = self._jpeg()
        self.users.write({"image_1920": photo})
        for user in self.users:
            self.env["zk.device.user"].create({
                "device_id": self.target.id, "pin": user.pin, "name": user.name,
            })
        self._wizard("photo_only").action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(cmd.command.startswith("DATA UPDATE USERPIC ") for cmd in commands))
        self.assertEqual(commands[1].depends_on_id, commands[0])

    def test_classic_photo_sync_is_pending_only(self):
        self.target.action_pull_profile_pictures()
        commands = self._commands()
        self.assertEqual(commands.mapped("command"), ["CHECK", "LOG"])
        self.assertEqual(commands[1].depends_on_id, commands[0])
