# -*- coding: utf-8 -*-
"""Security PUSH regression checks (run in Odoo's database test runner)."""
import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from ..controllers.security_push_codec import parse_tabledata, decode_biodata_record
from ..controllers.security_push_codec import server_biometric_support
from ..controllers.zk_push import ZKPushController
from ..models.security_push_transfer import _format_template


class TestSecurityPushProtocol(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.acc = cls.env["zk.device"].create({
            "name": "Protocol ACC test", "serial_number": "TEST-ACC-PUSH-36",
            "device_type": "acc", "is_approved": True, "tz": "UTC",
        })
        cls.legacy = cls.env["zk.device"].create({
            "name": "Protocol legacy test", "serial_number": "TEST-LEGACY-PUSH-36",
            "is_approved": True, "tz": "UTC",
        })

    def test_biometric_handshake_advertises_supported_templates_only(self):
        self.acc.write({"registry_payload": (
            "DeviceType=acc,MultiBioDataSupport=0:1:0:0:0:0:0:0:1:1:0,"
            "MultiBioPhotoSupport=0:0:0:0:0:0:0:0:0:1:0"
        )})
        data, photo = server_biometric_support(self.acc.registry_payload)
        self.assertEqual(data, "0:1:0:0:0:0:0:0:0:1:0")
        self.assertEqual(photo, "0:0:0:0:0:0:0:0:0:0:0")
        config = ZKPushController()._security_push_config(self.acc)
        self.assertIn("MultiBioDataSupport=" + data + "\r\n", config)
        self.assertIn("MultiBioPhotoSupport=" + photo + "\r\n", config)

    def test_missing_biometric_registration_fails_closed(self):
        data, photo = server_biometric_support("")
        self.assertEqual(data, "0:0:0:0:0:0:0:0:0:0:0")
        self.assertEqual(photo, data)
        malformed, _ = server_biometric_support("MultiBioDataSupport=0:1")
        self.assertEqual(malformed, data)

    def test_negotiation_does_not_enable_unadvertised_types(self):
        data, photo = server_biometric_support(
            "MultiBioDataSupport=0:0:0:0:0:0:0:0:1:1:0,"
            "MultiBioPhotoSupport=0:0:0:0:0:0:0:0:0:1:0"
        )
        self.assertEqual(data, "0:0:0:0:0:0:0:0:0:1:0")
        self.assertEqual(photo, "0:0:0:0:0:0:0:0:0:0:0")

    def test_security_pull_queues_three_separate_tables(self):
        self.acc.action_pull_users()
        commands = self.env["zk.device.command"].search([
            ("device_id", "=", self.acc.id),
        ], order="id")
        self.assertEqual(len(commands), 3)
        self.assertEqual([x.command for x in commands], [
            "DATA QUERY tablename=user,fielddesc=*,filter=*",
            "DATA QUERY tablename=biodata,fielddesc=*,filter=Type=1",
            "DATA QUERY tablename=biodata,fielddesc=*,filter=Type=9",
        ])

    def test_security_push_rejects_unsupported_historical_attendance_pull(self):
        with self.assertRaises(UserError):
            self.acc.action_pull_attendance()
        self.assertFalse(self.env["zk.device.command"].search([
            ("device_id", "=", self.acc.id),
            ("command", "like", "DATA QUERY ATTLOG%"),
        ]))

    def test_legacy_pull_command_is_unchanged(self):
        self.legacy.action_pull_users()
        command = self.env["zk.device.command"].search([
            ("device_id", "=", self.legacy.id),
        ], limit=1)
        self.assertEqual(command.command, "DATA QUERY USERINFO")

    def test_security_ack_accepts_positive_record_count(self):
        cmd = self.acc.queue_adms_command(
            "DATA QUERY tablename=user,fielddesc=*,filter=*", "Test pull"
        )
        self.acc.next_adms_command()
        self.acc.acknowledge_adms_command(cmd.command_id, "8")
        self.assertEqual(cmd.state, "done")
        self.assertEqual(cmd.return_code, "8")

    def test_security_ack_rejects_error_code(self):
        cmd = self.acc.queue_adms_command(
            "DATA QUERY tablename=user,fielddesc=*,filter=*", "Test rejection"
        )
        self.acc.next_adms_command()
        self.acc.acknowledge_adms_command(cmd.command_id, "-629")
        self.assertEqual(cmd.state, "failed")
        self.assertEqual(cmd.return_code, "-629")

    def test_remote_restart_is_queued_only_when_device_is_idle(self):
        action = self.acc.action_restart_device()
        command = self.env["zk.device.command"].search([
            ("device_id", "=", self.acc.id), ("command", "=", "REBOOT"),
        ], limit=1)
        self.assertEqual(command.operation, "Restart device")
        self.assertEqual(command.state, "pending")
        self.assertEqual(action["params"]["type"], "warning")

        with self.assertRaises(UserError):
            self.acc.action_restart_device()

    def test_unapproved_device_cannot_queue_security_user_query(self):
        self.acc.is_approved = False
        try:
            with self.assertRaises(UserError):
                self.acc.action_pull_users()
        finally:
            self.acc.is_approved = True

    def test_security_template_is_only_stored_in_private_generic_cache(self):
        encoded = base64.b64encode(b"sample-fixture-not-real-biometric").decode("ascii")
        record = decode_biodata_record({
            "pin": "101", "type": "1", "no": "2", "valid": "0", "tmp": encoded,
            "majorver": "13", "minorver": "0", "format": "0",
        })
        template = self.env["zk.device.biometric.template"].sudo().upsert_from_adms(
            self.acc, record,
        )
        self.assertEqual(template.biometric_type, "fingerprint")
        self.assertEqual(template.valid, 0)
        self.assertFalse(self.env["zk.device.fingerprint"].sudo().search([
            ("device_id", "=", self.acc.id), ("pin", "=", "101"),
        ]))

    def test_user_rows_are_case_normalized_and_pin_is_per_device(self):
        rows = parse_tabledata(
            "user UID=9\tCardNo=0\tPin=78\tName=Mary Jones\tPrivilege=0\n", "user"
        )
        self.assertEqual(rows[0]["name"], "Mary Jones")
        user = self.env["zk.device.user"].sudo().upsert_from_adms(self.acc, rows[0])
        self.assertFalse(user.employee_id)
        self.assertEqual(user.pin, "78")

    def test_legacy_push_to_access_device_is_blocked(self):
        user = self.env["zk.device.user"].create({
            "device_id": self.legacy.id, "pin": "901", "name": "Test user",
        })
        with self.assertRaises(UserError):
            user._queue_transfer_to_device(self.acc)

    def test_security_profile_only_uses_safe_normal_user_fields(self):
        """Never copy administrator status, passwords, cards, or biometric bytes."""
        self.acc.write({"registry_payload": "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,MaxPackageSize=2048000"})
        target = self.env["zk.device"].create({
            "name": "Target ACC 37", "serial_number": "TEST-ACC-TARGET-37",
            "device_type": "acc", "is_approved": True,
            "company_id": self.acc.company_id.id,
            "registry_payload": self.acc.registry_payload,
            "last_user_sync_at": self.env["zk.device"]._online_cutoff(),
        })
        user = self.env["zk.device.user"].create({
            "device_id": self.acc.id, "pin": "201", "name": "Normal Employee",
            "privilege": 0, "card": "123456", "password": "do-not-transfer",
        })
        user._queue_security_push_transfer(target, "profile_only", 2, 1, 1)
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id)
        ], order="id asc", limit=1)
        self.assertEqual(command.state, "pending")
        self.assertIn("DATA UPDATE user ", command.command)
        self.assertIn("Pin=201", command.command)
        self.assertIn("Privilege=0", command.command)
        self.assertNotIn("do-not-transfer", command.command)
        self.assertNotIn("123456", command.command)
        authorize = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id), ("depends_on_id", "=", command.id),
        ], limit=1)
        self.assertEqual(authorize.command, (
            "DATA UPDATE userauthorize Pin=201\tAuthorizeTimezoneId=2\tAuthorizeDoorId=1"
        ))
        verify = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id), ("depends_on_id", "=", authorize.id),
        ], limit=1)
        self.assertEqual(verify.command, "DATA QUERY tablename=user,fielddesc=*,filter=Pin=201")
        self.assertNotIn("StartTime=0", command.command)
        self.assertNotIn("EndTime=0", command.command)

    def test_admin_source_enrolls_normal_target_and_existing_pin_is_blocked(self):
        target = self.env["zk.device"].create({
            "name": "Target ACC 37b", "serial_number": "TEST-ACC-TARGET-37B",
            "device_type": "acc", "is_approved": True,
            "company_id": self.acc.company_id.id,
            "last_user_sync_at": self.env["zk.device"]._online_cutoff(),
        })
        admin = self.env["zk.device.user"].create({
            "device_id": self.acc.id, "pin": "202", "name": "Admin",
            "privilege": 14, "password": "private-admin-secret",
        })
        self.assertEqual(admin._queue_security_push_transfer(target, "profile_only", 2, 1, 1), 3)
        command = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id),
        ], order="id asc", limit=1)
        self.assertIn("Privilege=0", command.command)
        self.assertNotIn("Privilege=14", command.command)
        self.assertNotIn("private-admin-secret", command.command)
        # Keep a fresh inventory as an explicit identity/PIN conflict check.
        self.env["zk.device.user"].create({
            "device_id": target.id, "pin": "202", "name": "Different person",
        })
        with self.assertRaises(UserError):
            admin._queue_security_push_transfer(target, "profile_only", 2, 1, 1)

    def test_command_allocator_handles_stale_sequence(self):
        first = self.acc.queue_adms_command("DATA QUERY tablename=user,fielddesc=*,filter=*", "First")
        self.acc.adms_command_sequence = 0
        second = self.acc.queue_adms_command("DATA QUERY tablename=user,fielddesc=*,filter=*", "Second")
        self.assertEqual(second.command_id, first.command_id + 1)

    def test_biometric_metadata_round_trip(self):
        encoded = base64.b64encode(b"fake fixture -- not a real fingerprint").decode("ascii")
        values = decode_biodata_record({
            "pin": "203", "type": "1", "no": "4", "index": "0", "valid": "1",
            "duress": "0", "tmp": encoded, "majorver": "13",
            "minorver": "0", "format": "0",
        })
        record = self.env["zk.device.biometric.template"].sudo().upsert_from_adms(self.acc, values)
        self.assertTrue(record.security_metadata_complete)
        self.assertEqual(record.security_no, 4)
        self.assertEqual(record.security_index, 0)
        self.assertEqual(record.security_type, 1)
        self.assertEqual(record.template_index, 4)

    def test_biometric_update_uses_canonical_security_push_field_names(self):
        registry = (
            "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
            "MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,MaxPackageSize=2048000"
        )
        self.acc.registry_payload = registry
        target = self.env["zk.device"].create({
            "name": "Canonical payload target", "serial_number": "TEST-CANONICAL-41",
            "device_type": "acc", "is_approved": True,
            "company_id": self.acc.company_id.id, "registry_payload": registry,
        })
        encoded = base64.b64encode(b"safe non-biometric test fixture").decode("ascii")
        template = type("Template", (), {
            "security_metadata_complete": True, "security_type": 9,
            "biometric_type": "face", "security_format": 0,
            "security_duress": 0, "valid": 1, "template": encoded,
            "template_size": len(base64.b64decode(encoded)),
            "template_version": "36.1;format=0", "security_no": 0,
            "security_index": 0, "pin": "9",
        })()
        command = _format_template(self.acc, target, template)
        self.assertTrue(command.startswith("DATA UPDATE biodata Pin=9\tNo=0\tIndex=0"))
        self.assertIn("\tMajorVer=36\tMinorVer=1\tFormat=0\tTmp=", command)

    def test_dependency_blocks_templates_until_profile_ack(self):
        first = self.acc.queue_adms_command(
            "DATA UPDATE user Pin=9\tName=Test", "Profile",
        )
        second = self.acc.queue_adms_command(
            "DATA UPDATE biodata pin=9\tno=0", "Template", depends_on=first,
        )
        self.assertEqual(self.acc.next_adms_command(), first)
        self.assertFalse(self.acc.next_adms_command())
        self.acc.acknowledge_adms_command(first.command_id, "-629")
        self.assertFalse(self.acc.next_adms_command())
        self.assertEqual(second.state, "cancelled")

    def test_dependency_delivers_after_ack(self):
        first = self.acc.queue_adms_command("DATA UPDATE user Pin=9\tName=Test", "Profile")
        second = self.acc.queue_adms_command("DATA UPDATE biodata pin=9\tno=0", "Template", depends_on=first)
        self.assertEqual(self.acc.next_adms_command(), first)
        self.acc.acknowledge_adms_command(first.command_id, "0")
        self.assertEqual(self.acc.next_adms_command(), second)

    def test_empty_target_user_query_is_valid_inventory_check(self):
        """Return=0 is a successful empty inventory without a querydata body."""
        target = self.env["zk.device"].create({
            "name": "Empty target ACC", "serial_number": "TEST-EMPTY-ACC-38",
            "device_type": "acc", "is_approved": True,
            "company_id": self.acc.company_id.id,
        })
        command = target.queue_adms_command(
            "DATA QUERY tablename=user,fielddesc=*,filter=*", "Pull user inventory",
        )
        target.next_adms_command()
        target.acknowledge_adms_command(command.command_id, "0")
        self.assertEqual(command.state, "done")
        self.assertFalse(target.last_user_sync_at)
        self.assertFalse(self.env["zk.device.user"].search_count([
            ("device_id", "=", target.id),
        ]))
        self.assertEqual(target._security_push_user_inventory_status(), "empty")

        user = self.env["zk.device.user"].create({
            "device_id": self.acc.id, "pin": "208", "name": "First Enrollee",
            "privilege": 0,
        })
        user._queue_security_push_transfer(target, "profile_only", 2, 1, 1)
        queued = self.env["zk.device.command"].search([
            ("device_id", "=", target.id), ("command", "ilike", "DATA UPDATE user"),
        ])
        self.assertEqual(len(queued), 1)
        self.assertIn("Pin=208", queued.command)

    def test_empty_target_requires_latest_successful_user_query(self):
        """An unrelated success, a failed user query, or stale proof is unsafe."""
        target = self.env["zk.device"].create({
            "name": "Unverified ACC", "serial_number": "TEST-UNVERIFIED-ACC-38",
            "device_type": "acc", "is_approved": True,
            "company_id": self.acc.company_id.id,
        })
        biometric = target.queue_adms_command(
            "DATA QUERY tablename=biodata,fielddesc=*,filter=Type=1",
            "Not a user inventory",
        )
        target.next_adms_command()
        target.acknowledge_adms_command(biometric.command_id, "0")
        self.assertFalse(target._security_push_user_inventory_status())

        users = target.queue_adms_command(
            "DATA QUERY tablename=user,fielddesc=*,filter=*", "Failed inventory",
        )
        target.next_adms_command()
        target.acknowledge_adms_command(users.command_id, "-629")
        self.assertFalse(target._security_push_user_inventory_status())

    def test_transfer_wizard_is_precreated_and_can_choose_empty_target(self):
        """The button must receive a real transient record, not an empty one."""
        user = self.env["zk.device.user"].create({
            "device_id": self.acc.id, "pin": "209", "name": "Wizard Enrollee",
            "privilege": 0,
        })
        action = user.action_open_transfer_wizard()
        self.assertEqual(action["res_model"], "zk.device.user.transfer.wizard")
        self.assertTrue(action.get("res_id"))
        self.assertEqual(action.get("context", {}).get("form_view_initial_mode"), "edit")
        wizard = self.env["zk.device.user.transfer.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.device_user_id, user)
        self.assertFalse(wizard.target_device_id)
        with self.assertRaises(UserError):
            wizard.action_transfer()  # User-friendly missing-target error, not ensure_one.


class TestSecurityPushUserPhotos(TransactionCase):
    """USERPIC is a device-local profile JPG, never a biometric template."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["zk.device"].create({
            "name": "Photo test access terminal", "serial_number": "TEST-USERPIC-48",
            "device_type": "acc", "is_approved": True, "tz": "UTC",
        })

    @staticmethod
    def _photo():
        from PIL import Image
        from io import BytesIO
        buf = BytesIO()
        Image.new("RGB", (12, 12), (70, 100, 150)).save(buf, format="JPEG")
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return encoded

    def test_userpic_accepts_security_push_wire_format(self):
        from ..controllers.security_push_codec import decode_userpic_record
        encoded = self._photo()
        packet = "userpic pin=9001\tfilename=9001.jpg\tsize=%s\tcontent=%s\n" % (
            len(encoded), encoded,
        )
        rows = parse_tabledata(packet, "userpic")
        self.assertEqual(len(rows), 1)
        result = decode_userpic_record(rows[0])
        self.assertEqual(result["pin"], "9001")
        self.assertTrue(base64.b64decode(result["image_1920"]).startswith(b"\xff\xd8\xff"))

    def test_userpic_accepts_content_on_following_line(self):
        from ..controllers.security_push_codec import decode_userpic_record
        encoded = self._photo()
        packet = "userpic pin=44\tfilename=44.jpg\tsize=%s\ncontent=%s\n" % (
            len(encoded), encoded,
        )
        self.assertEqual(decode_userpic_record(parse_tabledata(packet, "userpic")[0])["pin"], "44")

    def test_userpic_never_accepts_non_jpeg_or_broken_size(self):
        from ..controllers.security_push_codec import decode_userpic_record
        encoded = base64.b64encode(b"<html>not a jpeg</html>").decode("ascii")
        row = {"pin": "44", "filename": "44.jpg", "content": encoded, "size": str(len(encoded))}
        with self.assertRaises(ValueError):
            decode_userpic_record(row)
        row["size"] = str(len(encoded) + 1)
        with self.assertRaises(ValueError):
            decode_userpic_record(row)

    def test_userpic_must_have_device_specific_pin(self):
        from ..controllers.security_push_codec import decode_userpic_record
        encoded = self._photo()
        row = {"pin": "44\t999", "filename": "44.jpg", "content": encoded, "size": str(len(encoded))}
        with self.assertRaises(ValueError):
            decode_userpic_record(row)

    def test_userpic_can_be_saved_as_device_user_image_without_employee(self):
        from ..controllers.security_push_codec import decode_userpic_record
        encoded = self._photo()
        row = {"pin": "9001", "filename": "9001.jpg", "content": encoded, "size": str(len(encoded))}
        image = decode_userpic_record(row)["image_1920"]
        user = self.env["zk.device.user"].sudo().create({
            "device_id": self.device.id, "pin": "9001", "image_1920": image,
        })
        self.assertTrue(user.image_1920)
        self.assertFalse(user.employee_id)
        self.assertEqual(user.privilege, 0)

    def test_userpic_persists_to_exact_device_user_and_repeat_upserts(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        source = self.env["zk.device.user"].sudo().create({
            "device_id": self.device.id, "pin": "9001", "name": "Photo owner",
        })
        second = self.env["zk.device"].sudo().create({
            "name": "Unrelated terminal", "serial_number": "TEST-USERPIC-OTHER-48",
            "device_type": "acc", "is_approved": True,
        })
        unrelated = self.env["zk.device.user"].sudo().create({
            "device_id": second.id, "pin": "9001", "name": "Another person",
        })
        encoded = self._photo()
        packet = "userpic pin=9001\tfilename=9001.jpg\tsize=%s\tcontent=%s\n" % (
            len(encoded), encoded,
        )
        with patch("odoo.addons.tam_hr_zk_attendance.controllers.zk_push.request",
                   SimpleNamespace(env=self.env)):
            self.assertEqual(
                ZKPushController()._store_security_tabledata(self.device, "userpic", packet, 1), 1,
            )
            self.assertEqual(
                ZKPushController()._store_security_tabledata(self.device, "userpic", packet, 1), 1,
            )
        self.assertEqual(self.env["zk.device.user"].sudo().search_count([
            ("device_id", "=", self.device.id), ("pin", "=", "9001"),
        ]), 1)
        self.assertTrue(source.image_1920)
        self.assertFalse(unrelated.image_1920)
        with patch("odoo.addons.tam_hr_zk_attendance.controllers.zk_push.request",
                   SimpleNamespace(env=self.env)):
            with self.assertRaises(ValueError):
                ZKPushController()._store_security_tabledata(self.device, "userpic", packet, 2)

    def test_userpic_arriving_before_user_creates_unmapped_device_stub_only(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        encoded = self._photo()
        packet = "userpic pin=811\tfilename=811.jpg\tsize=%s\tcontent=%s\n" % (
            len(encoded), encoded,
        )
        with patch("odoo.addons.tam_hr_zk_attendance.controllers.zk_push.request",
                   SimpleNamespace(env=self.env)):
            self.assertEqual(
                ZKPushController()._store_security_tabledata(self.device, "userpic", packet, 1), 1,
            )
        stub = self.env["zk.device.user"].sudo().search([
            ("device_id", "=", self.device.id), ("pin", "=", "811"),
        ], limit=1)
        self.assertTrue(stub.image_1920)
        self.assertFalse(stub.employee_id)
        self.assertEqual(stub.privilege, 0)
