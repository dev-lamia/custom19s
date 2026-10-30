# -*- coding: utf-8 -*-
"""Version metadata parser, restricted protocol capture, and transfer authorization."""

import base64
import io

from PIL import Image
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from ..controllers.device_metadata import extract_registry_capabilities, extract_versions
from ..controllers.zk_push import ZKPushController
from ..models.security_push_transfer import _format_user_authorization, _format_profile, _format_profile_picture


class TestDeviceVersionCapture(TransactionCase):
    def test_registry_capability_allowlist_keeps_only_safe_technical_values(self):
        values = extract_registry_capabilities(
            "DeviceName=SpeedFace-V5L,FaceFunOn=1,FingerFunOn=1,"
            "MaxFingerCount=100,MaxUserFingerCount=10,"
            "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
            "MultiBioVersion=0:13:0:0:0:0:0:0:0:36:1:0,"
            "ZKFPVersion=13,SessionID=private,Password=private"
        )
        self.assertEqual(values["max_finger_count"], 100)
        self.assertTrue(values["face_function_enabled"])
        self.assertEqual(values["multi_biodata_support"], "0:1:0:0:0:0:0:0:0:1:0")
        self.assertNotIn("session_id", values)
        self.assertNotIn("password", values)

    def test_version_parsing_known_info_and_options(self):
        self.assertEqual(extract_versions(
            "ID=8&Return=0&CMD=INFO\r\nFWVersion=ZAM230-NF50VA-Ver1.3.9\r\n"
            "PushVersion=Ver 3.1.6S-20260115\r\nPassword=secret"
        ), {"firmware_version": "ZAM230-NF50VA-Ver1.3.9",
            "push_version": "Ver 3.1.6S-20260115"})
        self.assertEqual(extract_versions(
            "ID=8&Return=0&Content=ZAM230-NF50VA-Ver1.3.9", "FWVersion"
        ), {"firmware_version": "ZAM230-NF50VA-Ver1.3.9"})
        self.assertEqual(extract_versions("ID=9&Return=0&CMD=DATA", "PushVersion"), {})

    def test_do_not_accept_arbitrary_command_payload_or_secrets_as_versions(self):
        self.assertEqual(extract_versions("Password=secret&PrivateKey=abc&pushver=2.4.1"), {})
        self.assertEqual(extract_versions("FWVersion=Hello\nPassword=secret"), {})
        self.assertEqual(extract_versions("Content=Password=secret", "FWVersion"), {})
        self.assertEqual(extract_versions("FWVersion=***bad***"), {})
        self.assertEqual(extract_versions("FWVersion=" + "A" * 20000), {})

    def test_metadata_written_only_when_recognized_on_approved_device(self):
        device = self.env["zk.device"].create({
            "name": "Metadata test", "serial_number": "TEST-META-47",
            "device_type": "att", "is_approved": True,
        })
        controller = ZKPushController()
        self.assertFalse(controller._save_version_info(device, {}, "INFO"))
        self.assertFalse(device.last_metadata_at)
        self.assertTrue(controller._save_version_info(device, {
            "firmware_version": "ZAM230-NF50VA-Ver1.3.9",
            "push_version": "Ver 3.1.6S-20260115",
        }, "OPTIONS"))
        self.assertEqual(device.firmware_version, "ZAM230-NF50VA-Ver1.3.9")
        self.assertEqual(device.push_version, "Ver 3.1.6S-20260115")
        self.assertEqual(device.device_type, "att")
        self.assertTrue(device.last_metadata_at)
        self.assertEqual(device.metadata_source, "OPTIONS")


class TestUserAuthorizationTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = cls.env["zk.device"].create({
            "name": "Security source", "serial_number": "TEST-AUTH-SOURCE-47",
            "device_type": "acc", "is_approved": True,
        })
        cls.target = cls.env["zk.device"].create({
            "name": "Security target", "serial_number": "TEST-AUTH-TARGET-47",
            "device_type": "acc", "is_approved": True,
            "last_user_sync_at": cls.env["zk.device"]._online_cutoff(),
        })
        cls.user = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "name": "PIN 9001 Test", "pin": "9001",
            "privilege": 0,
        })

    def test_no_implicit_full_day_policy(self):
        for timezone in (0, 51, -1):
            with self.assertRaises(UserError):
                _format_user_authorization("9001", timezone, 1)
        with self.assertRaises(UserError):
            _format_user_authorization("9001", 1, 0)
        with self.assertRaises(UserError):
            _format_user_authorization("9001", True, 1)
        self.assertEqual(
            _format_user_authorization("9001", 2, 1),
            "DATA UPDATE userauthorize Pin=9001\tAuthorizeTimezoneId=2\tAuthorizeDoorId=1",
        )
        self.assertNotIn("StartTime=0", _format_profile(self.user))

    def test_profile_requires_explicit_rule_and_depends_on_authorization(self):
        with self.assertRaises(UserError):
            self.user._queue_security_push_transfer(self.target, "profile_only")
        self.assertFalse(self.env["zk.device.command"].search([
            ("device_id", "=", self.target.id)
        ]))
        self.assertEqual(self.user._queue_security_push_transfer(
            self.target, "profile_only", 2, 1, 1,
        ), 3)
        commands = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id)
        ], order="id asc")
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[1].depends_on_id, commands[0])
        self.assertEqual(commands[2].depends_on_id, commands[1])
        self.assertIn("AuthorizeTimezoneId=2", commands[1].command)
        commands[0].write({"state": "sent"})
        self.target.acknowledge_adms_command(commands[0].command_id, "0")
        commands[1].write({"state": "sent"})
        self.target.acknowledge_adms_command(commands[1].command_id, "-1")
        self.assertEqual(commands[1].state, "failed")
        self.assertFalse(self.target.next_adms_command())
        self.assertEqual(commands[2].state, "cancelled")

    def test_authorize_existing_user_does_not_resend_profiles_or_templates(self):
        self.env["zk.device.user"].create({
            "device_id": self.target.id, "name": "PIN 9001 Test", "pin": "9001",
            "privilege": 0,
        })
        self.assertEqual(self.user._queue_security_push_transfer(
            self.target, "authorize_only", 2, 1,
        ), 1)
        cmd = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id)
        ], limit=1)
        self.assertTrue(cmd.command.startswith("DATA UPDATE userauthorize "))
        self.assertNotIn("biodata", cmd.command)


class TestSecurityPictureAndFaceRepair(TransactionCase):
    """No implicit re-enrollment or mismatched-PIN picture injection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registry = (
            "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
            "MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,"
            "MaxPackageSize=2048000"
        )
        cls.source = cls.env["zk.device"].create({
            "name": "Photo source", "serial_number": "TEST-XFER-PIC-SRC-52",
            "device_type": "acc", "is_approved": True,
            "registry_payload": cls.registry,
        })
        cls.target = cls.env["zk.device"].create({
            "name": "Photo target", "serial_number": "TEST-XFER-PIC-DST-52",
            "device_type": "acc", "is_approved": True,
            "last_user_sync_at": cls.env["zk.device"]._online_cutoff(),
            "registry_payload": cls.registry,
        })
        cls.source_user = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "pin": "2005",
            "name": "Mahdi Qarooni", "privilege": 0,
        })
        cls.target_user = cls.env["zk.device.user"].create({
            "device_id": cls.target.id, "pin": "2005",
            "name": "Mahdi Qarooni", "privilege": 0,
        })

    def _photo(self):
        out = io.BytesIO()
        Image.new("RGB", (32, 24), "white").save(out, format="JPEG")
        return base64.b64encode(out.getvalue())

    def test_photo_only_never_enrolls_user_or_changes_target_cache(self):
        self.source_user.image_1920 = self._photo()
        self.assertFalse(self.target_user.image_1920)
        self.assertEqual(self.source_user._queue_security_push_transfer(
            self.target, "photo_only",
        ), 1)
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id)
        ], limit=1)
        self.assertTrue(command.command.startswith("DATA UPDATE userpic pin=2005\tsize="))
        self.assertIn("\tformat=0\tcontent=", command.command)
        self.assertNotIn("DATA UPDATE biodata", command.command)
        self.assertFalse(self.target_user.image_1920)
        self.assertEqual(command.state, "pending")
        self.assertEqual(self.target_user.privilege, 0)

    def test_photo_only_does_not_guess_or_create_target_user(self):
        self.source_user.image_1920 = self._photo()
        self.target_user.unlink()
        with self.assertRaises(UserError):
            self.source_user._queue_security_push_transfer(self.target, "photo_only")
        self.assertFalse(self.env["zk.device.command"].search([
            ("device_id", "=", self.target.id)
        ]))

    def test_photo_requires_source_picture_and_supported_package(self):
        with self.assertRaises(UserError):
            self.source_user._queue_security_push_transfer(self.target, "photo_only")
        self.source_user.image_1920 = self._photo()
        self.target.registry_payload = "MaxPackageSize=50"
        with self.assertRaises(UserError):
            _format_profile_picture(self.target, self.source_user.pin, self.source_user.image_1920)

    def test_face_only_requires_source_type_9_and_does_not_send_fingerprints(self):
        with self.assertRaises(UserError):
            self.source_user._queue_security_push_transfer(self.target, "face_only")
        self.env["zk.device.biometric.template"].sudo().create({
            "device_id": self.source.id, "pin": "2005",
            "biometric_type": "face", "template_index": 0,
            "template_version": "36.1", "template_size": 4,
            "template": base64.b64encode(b"FACE"),
            "security_no": 0, "security_index": 0,
            "security_format": 0, "security_duress": 0,
            "security_type": 9, "security_metadata_complete": True,
            "valid": 1,
        })
        self.assertEqual(self.source_user._queue_security_push_transfer(
            self.target, "face_only",
        ), 1)
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id)
        ], limit=1)
        self.assertTrue(command.command.startswith("DATA UPDATE biodata "))
        self.assertIn("\tType=9\t", command.command)
        self.assertNotIn("userpic", command.command)

    def test_photo_repair_checks_identity_before_queuing(self):
        self.source_user.image_1920 = self._photo()
        self.target_user.name = "Different person"
        with self.assertRaises(UserError):
            self.source_user._queue_security_push_transfer(self.target, "photo_only")
