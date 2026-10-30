# -*- coding: utf-8 -*-
"""Classic Attendance PUSH Type 9 face and normal-role bulk regression tests."""
import base64
import io

from PIL import Image
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


METADATA = (
    "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
    "MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,"
    "MaxPackageSize=2048000"
)


class TestClassicNativeFaceTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        common = {"is_approved": True, "company_id": cls.env.company.id,
                  "device_type": "att", "registry_payload": METADATA}
        cls.source = cls.env["zk.device"].create({
            **common, "name": "ATT native face source",
            "serial_number": "TEST-CLASSIC-FACE-SRC-61",
        })
        cls.target = cls.env["zk.device"].create({
            **common, "name": "ATT native face target",
            "serial_number": "TEST-CLASSIC-FACE-DST-61",
            "last_user_sync_at": fields.Datetime.now(),
        })
        cls.person = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "pin": "2005",
            "name": "MAHDI QAROONI", "privilege": 14,
        })

    def _face(self, user=None, version="36.1", template_index=0):
        user = user or self.person
        return self.env["zk.device.biometric.template"].sudo().create({
            "device_id": self.source.id, "pin": user.pin,
            "biometric_type": "face", "security_type": 9,
            "template_index": template_index, "template_version": version + ";format=0",
            "template_size": 8, "template": base64.b64encode(b"FACEDATA"),
            "security_no": 0, "security_index": template_index,
            "security_format": 0, "security_duress": 0,
            "valid": 1, "security_metadata_complete": True,
        })

    def _photo(self):
        stream = io.BytesIO()
        Image.new("RGB", (24, 24), "white").save(stream, format="JPEG")
        return base64.b64encode(stream.getvalue())

    def _commands(self):
        return self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id asc")

    def test_full_transfer_admin_becomes_normal_with_native_face_and_photo(self):
        self._face()
        self.env["zk.device.fingerprint"].sudo().create({
            "device_id": self.source.id, "pin": "2005", "finger_id": 1,
            "template_size": 4, "template": base64.b64encode(b"FPRT"),
        })
        self.person.image_1920 = self._photo()
        self.assertEqual(self.person._queue_classic_adms_transfer(
            self.target, preflight_only=True,
        ), 0)
        self.assertEqual(len(self._commands()), 0)
        self.assertEqual(self.person._queue_classic_adms_transfer(self.target), 5)
        commands = self._commands()
        self.assertEqual(len(commands), 5)
        self.assertIn("Pri=0", commands[0].command)
        self.assertNotIn("Pri=14", commands[0].command)
        self.assertEqual(commands[1].command, "DATA QUERY USERINFO PIN=2005")
        self.assertTrue(commands[2].command.startswith("DATA FP PIN=2005"))
        self.assertTrue(commands[3].command.startswith(
            "DATA UPDATE biodata Pin=2005\tNo=0\tIndex=0\tValid=1\tDuress=0\tType=9\tMajorVer=36\tMinorVer=1\tFormat=0\tTmp="
        ))
        self.assertTrue(commands[4].command.startswith("DATA UPDATE USERPIC PIN=2005"))
        for current, previous in zip(commands[1:], commands[:-1]):
            self.assertEqual(current.depends_on_id, previous)

    def test_face_only_repairs_existing_normal_user_without_photo_or_fp(self):
        self._face()
        self.person.image_1920 = self._photo()
        self.env["zk.device.user"].create({
            "device_id": self.target.id, "pin": "2005",
            "name": "MAHDI QAROONI", "privilege": 0,
        })
        self.assertEqual(self.person._queue_classic_adms_transfer(
            self.target, transfer_mode="face_only"
        ), 1)
        commands = self._commands()
        self.assertEqual(len(commands), 1)
        self.assertIn("Type=9", commands.command)
        self.assertNotIn("USERPIC", commands.command)
        self.assertNotIn("DATA FP", commands.command)
        self.assertNotIn("Pri=", commands.command)

    def test_face_algorithm_mismatch_refuses_all_commands(self):
        self._face()
        self.target.write({"registry_payload": METADATA.replace("36.1", "35.1")})
        with self.assertRaisesRegex(UserError, "algorithm versions differ"):
            self.person._queue_classic_adms_transfer(self.target)
        self.assertFalse(self._commands())

    def test_batch_preflights_all_selected_users_and_chains_face_uploads(self):
        another = self.env["zk.device.user"].create({
            "device_id": self.source.id, "pin": "2006",
            "name": "Second Person", "privilege": 14,
        })
        self._face()
        self._face(user=another)
        wizard = self.env["zk.device.user.batch.transfer.wizard"].create({
            "device_user_ids": [(6, 0, [self.person.id, another.id])],
            "source_device_id": self.source.id,
            "target_device_id": self.target.id,
            "transfer_mode": "full", "confirm_transfer": True,
        })
        wizard.action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 6)
        self.assertEqual(len(commands.filtered(lambda c: "Pri=0" in c.command)), 2)
        self.assertEqual(len(commands.filtered(lambda c: "Type=9" in c.command)), 2)
        for current, previous in zip(commands[1:], commands[:-1]):
            self.assertEqual(current.depends_on_id, previous)

    def test_batch_mismatch_second_user_rejects_before_any_command(self):
        another = self.env["zk.device.user"].create({
            "device_id": self.source.id, "pin": "2006",
            "name": "Second Person", "privilege": 14,
        })
        self._face()
        self._face(user=another, version="35.1")
        wizard = self.env["zk.device.user.batch.transfer.wizard"].create({
            "device_user_ids": [(6, 0, [self.person.id, another.id])],
            "source_device_id": self.source.id,
            "target_device_id": self.target.id,
            "transfer_mode": "full", "confirm_transfer": True,
        })
        with self.assertRaises(UserError):
            wizard.action_transfer()
        self.assertFalse(self._commands())

    def test_batch_face_only_repair_requires_target_user(self):
        self._face()
        wizard = self.env["zk.device.user.batch.transfer.wizard"].create({
            "device_user_ids": [(6, 0, [self.person.id])],
            "source_device_id": self.source.id,
            "target_device_id": self.target.id,
            "transfer_mode": "face_only", "confirm_transfer": True,
        })
        with self.assertRaises(UserError):
            wizard.action_transfer()
        self.assertFalse(self._commands())

    def test_classic_biodata_upload_is_cached_without_exposing_payload(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..controllers import zk_push

        raw = ("BIODATA Pin=2005\tNo=0\tIndex=0\tValid=1\tDuress=0"
               "\tType=9\tMajorVer=36\tMinorVer=1\tFormat=0\tTmp=RkFDRURBVEE=")
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            count = zk_push.ZKPushController()._store_classic_biodata(self.source, raw)
        self.assertEqual(count, 1)
        face = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", self.source.id), ("pin", "=", "2005"),
            ("biometric_type", "=", "face"),
        ])
        self.assertEqual(len(face), 1)
        self.assertEqual(face.security_type, 9)
        self.assertTrue(face.security_metadata_complete)
        self.assertEqual(face.template_version, "36.1;format=0")

    def test_classic_legacy_face_upload_uses_face_not_biodata(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..controllers import zk_push

        encoded = base64.b64encode(b"0123456789ABCDEF" + b"FACETEMPLATE").decode("ascii")
        record = "FACE PIN=2005\tFID=50\tSIZE=%d\tVALID=1\tTMP=%s" % (len(encoded), encoded)
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            result = zk_push.ZKPushController()._store_operlog_payload(self.source, record)
        self.assertEqual(result, (0, 0, 0))
        templates = self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", self.source.id), ("pin", "=", "2005"),
            ("biometric_type", "=", "face"),
        ])
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates.template_version, "classic-face")
        self.assertEqual(self.person._queue_classic_adms_transfer(
            self.target, "full"
        ), 3)
        commands = self._commands()
        self.assertTrue(commands[2].command.startswith("DATA UPDATE FACE PIN=2005"))
        self.assertNotIn("BIODATA", commands[2].command)

    def test_malformed_classic_face_fails_closed_without_creating_cache(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..controllers import zk_push

        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            with self.assertRaises(ValueError):
                zk_push.ZKPushController()._store_operlog_payload(
                    self.source, "FACE PIN=2005\tFID=0\tSIZE=4\tVALID=1\tTMP=bad!"
                )
        self.assertFalse(self.env["zk.device.biometric.template"].sudo().search([
            ("device_id", "=", self.source.id), ("pin", "=", "2005"),
        ]))
