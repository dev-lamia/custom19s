# -*- coding: utf-8 -*-
"""Classic Attendance PUSH can upload device-local profile pictures in OPERLOG."""
import base64
import io
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from odoo.tests.common import TransactionCase

from ..controllers import zk_push


class TestClassicUserPicture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["zk.device"].sudo().create({
            "name": "Classic photo test", "serial_number": "TEST-CLASSIC-PIC-2026",
            "tz": "UTC", "device_type": "att", "is_approved": True,
        })

    def test_classic_operlog_photo_is_private_and_device_scoped(self):
        output = io.BytesIO()
        Image.new("RGB", (8, 8), (24, 31, 88)).save(output, format="JPEG")
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        record = (
            "USERPIC PIN=7008\tFileName=7008.jpg\tSize=%s\tContent=%s" %
            (len(encoded), encoded)
        )
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            result = zk_push.ZKPushController()._store_operlog_payload(self.device, record)
        self.assertEqual(result, (0, 0, 1))
        user = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", self.device.id), ("pin", "=", "7008"),
        ])
        self.assertEqual(len(user), 1)
        self.assertTrue(user.image_1920)
        self.assertFalse(user.employee_id)
        self.assertFalse(user.name)
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            self.assertEqual(zk_push.ZKPushController()._store_operlog_payload(self.device, record), (0, 0, 1))
        self.assertEqual(self.env["zk.device.user"].sudo().search_count([
            ("device_id", "=", self.device.id), ("pin", "=", "7008"),
        ]), 1)

    def test_classic_photo_handshake_is_automatic_and_device_scoped(self):
        controller = zk_push.ZKPushController()
        self.assertNotIn("classic_userpic_upload", self.device._fields)
        self.assertEqual(controller._classic_trans_flag(self.device), "1111000001")
        self.device.write({"device_type": False})
        self.assertEqual(controller._classic_trans_flag(self.device), "1111000001")
        self.device.write({"device_type": "att"})
        self.device.write({"is_approved": False})
        self.assertEqual(controller._classic_trans_flag(self.device), "1111000000")
        self.device.write({"is_approved": True, "device_type": "acc"})
        self.assertEqual(controller._classic_trans_flag(self.device), "1111000000")

    def test_classic_single_pin_query_requires_matching_user_payload(self):
        self.device.write({"is_approved": True, "device_type": "att"})
        command = self.device.queue_adms_command(
            "DATA QUERY USERINFO PIN=1008", "Strict PIN 1008 diagnostic",
        )
        command.write({"state": "sent"})
        self.assertFalse(self.device.complete_query_from_payload(
            "DATA QUERY USERINFO", received_user_pins={"1010"},
        ))
        self.assertEqual(command.state, "sent")
        self.assertFalse(self.device.complete_query_from_payload(
            "DATA QUERY USERINFO", received_user_pins=set(),
        ))
        self.assertEqual(command.state, "sent")
        result = self.device.complete_query_from_payload(
            "DATA QUERY USERINFO", received_user_pins={"1008"},
        )
        self.assertEqual(result, command)
        self.assertEqual(command.state, "done")
        self.assertEqual(command.return_code, "payload_received")
        self.assertTrue(command.last_payload_at)

    def test_classic_operlog_diagnostic_logs_only_counts(self):
        payload = "USERPIC PIN=7008\tFileName=secret.jpg\tContent=SECRET_PHOTO_BYTES\n"
        with patch.object(zk_push, "_logger") as logger:
            zk_push.ZKPushController()._log_payload_summary(
                self.device.serial_number, "OPERLOG", payload,
            )
        message, *args = logger.info.call_args.args
        self.assertIn("picture_records=%s", message)
        self.assertEqual(args[-1], 1)
        self.assertNotIn("SECRET_PHOTO_BYTES", str(logger.info.call_args))
        self.assertNotIn("secret.jpg", str(logger.info.call_args))
