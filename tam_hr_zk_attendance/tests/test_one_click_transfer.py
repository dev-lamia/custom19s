# -*- coding: utf-8 -*-
"""v0.53 regression tests, runnable in an Odoo 19 test database."""
import base64
import io

from PIL import Image
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestOneClickSecurityPushTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        metadata = (
            "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
            "MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,"
            "MaxPackageSize=2048000"
        )
        cls.source = cls.env["zk.device"].create({
            "name": "Full transfer source", "serial_number": "TEST-FULL-SOURCE-53",
            "device_type": "acc", "is_approved": True,
            "registry_payload": metadata,
        })
        cls.target = cls.env["zk.device"].create({
            "name": "Full transfer destination", "serial_number": "TEST-FULL-TARGET-53",
            "device_type": "acc", "is_approved": True,
            "registry_payload": metadata,
            "last_user_sync_at": cls.env["zk.device"]._online_cutoff(),
        })
        cls.person = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "name": "Device Test Person",
            "pin": "9012", "privilege": 0,
        })

    @staticmethod
    def _jpeg():
        stream = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(stream, format="JPEG")
        return base64.b64encode(stream.getvalue())

    def _template(self, kind):
        number, name, version = kind
        return self.env["zk.device.biometric.template"].sudo().create({
            "device_id": self.source.id, "pin": "9012",
            "biometric_type": name, "template_index": 0,
            "template_version": version, "template_size": 4,
            "template": base64.b64encode(b"DATA"),
            "security_no": 0, "security_index": 0,
            "security_format": 0, "security_duress": 0,
            "security_type": number, "security_metadata_complete": True,
            "valid": 1,
        })

    def _commands(self):
        return self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id asc")

    def test_new_user_one_click_enqueues_sequential_profile_biometrics_photo(self):
        self._template((1, "fingerprint", "13.0"))
        self._template((9, "face", "36.1"))
        self.person.image_1920 = self._jpeg()
        wizard = self.env["zk.device.user.transfer.wizard"].create({
            "device_user_id": self.person.id,
            "target_device_id": self.target.id,
            "confirm_transfer": True,
        })
        self.assertEqual(wizard.transfer_mode, "full")
        self.assertEqual((wizard.authorization_group_id,
                          wizard.authorization_timezone_id,
                          wizard.authorization_door_id), (1, 1, 1))
        wizard.action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 6)
        self.assertTrue(commands[0].command.startswith("DATA UPDATE user "))
        self.assertIn("Privilege=0", commands[0].command)
        self.assertIn("AuthorizeTimezoneId=1", commands[1].command)
        self.assertIn("AuthorizeDoorId=1", commands[1].command)
        self.assertTrue(commands[2].command.startswith("DATA QUERY tablename=user,"))
        self.assertIn("Type=1", commands[3].command)
        self.assertIn("Type=9", commands[4].command)
        self.assertTrue(commands[5].command.startswith("DATA UPDATE userpic "))
        for i in range(1, len(commands)):
            self.assertEqual(commands[i].depends_on_id, commands[i-1])
        self.assertEqual(self.target.next_adms_command(), commands[0])
        self.assertFalse(self.target.next_adms_command())
        # A successful user query ACK alone must not unlock biometrics:
        # the target must actually return a matching normal user record.
        commands[0].write({"state": "done", "return_code": "0"})
        commands[1].write({"state": "done", "return_code": "0"})
        commands[2].write({"state": "done", "return_code": "1",
                           "sent_at": commands[0].sent_at})
        self.assertFalse(self.target.next_adms_command())
        self.env["zk.device.user"].sudo().upsert_from_adms(self.target, {
            "pin": "9012", "name": "Device Test Person", "pri": 0,
        })
        self.assertEqual(self.target.next_adms_command(), commands[3])

    def test_missing_photos_and_templates_do_not_block_basic_transfer(self):
        count = self.person._queue_security_push_transfer(
            self.target, "full", 1, 1, 1,
        )
        self.assertEqual(count, 3)
        self.assertEqual(len(self._commands()), 3)

    def test_existing_matching_target_skips_profile_and_keeps_identity(self):
        target_user = self.env["zk.device.user"].create({
            "device_id": self.target.id, "name": "Device Test Person",
            "pin": "9012", "privilege": 0,
        })
        self.person.image_1920 = self._jpeg()
        count = self.person._queue_security_push_transfer(
            self.target, "full", 1, 1, 1,
        )
        self.assertEqual(count, 3)
        commands = self._commands()
        self.assertEqual(len(commands), 3)
        self.assertTrue(commands[0].command.startswith("DATA UPDATE userauthorize "))
        self.assertTrue(commands[1].command.startswith("DATA QUERY tablename=user,"))
        self.assertTrue(commands[2].command.startswith("DATA UPDATE userpic "))
        self.assertFalse(target_user.image_1920)  # Do not report unverified receipt

    def test_conflicting_user_never_queues_any_command(self):
        self.env["zk.device.user"].create({
            "device_id": self.target.id, "name": "Different Person",
            "pin": "9012", "privilege": 0,
        })
        with self.assertRaises(UserError):
            self.person._queue_security_push_transfer(self.target, "full", 1, 1, 1)
        self.assertFalse(self._commands())

    def test_invalid_template_never_leaves_partial_profile(self):
        self._template((9, "face", "35.1"))
        with self.assertRaises(UserError):
            self.person._queue_security_push_transfer(self.target, "full", 1, 1, 1)
        self.assertFalse(self._commands())

    def test_acc_update_name_uses_nonlegacy_noncredential_command(self):
        self.person.action_update_device_name()
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.source.id),
        ], limit=1)
        self.assertEqual(command.command, "DATA UPDATE user Pin=9012\tName=Device Test Person")
        self.assertNotIn("Password=", command.command)
        self.assertNotIn("Privilege=", command.command)
        self.assertNotIn("Group=", command.command)
