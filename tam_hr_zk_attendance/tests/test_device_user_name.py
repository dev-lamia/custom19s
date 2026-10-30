# -*- coding: utf-8 -*-
"""Device User Name is a live, device-specific and non-destructive raw-log label."""
from odoo.tests.common import TransactionCase


class TestRawPunchDeviceUserName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Device = cls.env["zk.device"].sudo()
        cls.device_a = Device.create({
            "name": "Name test A", "serial_number": "TEST-NAME-A-2026", "tz": "UTC",
        })
        cls.device_b = Device.create({
            "name": "Name test B", "serial_number": "TEST-NAME-B-2026", "tz": "UTC",
        })
        cls.User = cls.env["zk.device.user"].sudo()
        cls.Raw = cls.env["zk.machine.attendance"].sudo()

    def _raw(self, device, pin, time):
        return self.Raw.create({
            "device_id": device.id, "device_id_num": pin,
            "punch_type": "0", "punching_time": time,
        })

    def test_name_is_from_exact_device_pin_even_if_employee_missing(self):
        user_a = self.User.create({
            "device_id": self.device_a.id, "pin": "1008", "name": "Name from A",
        })
        self.User.create({
            "device_id": self.device_b.id, "pin": "1008", "name": "Different name B",
        })
        record_a = self._raw(self.device_a, "1008", "2026-10-12 08:00:00")
        record_b = self._raw(self.device_b, "1008", "2026-10-12 08:01:00")
        unknown = self._raw(self.device_a, "9999", "2026-10-12 08:02:00")
        by_id = {row.id: row.device_user_name for row in (record_a | record_b | unknown)}
        self.assertEqual(by_id[record_a.id], "Name from A")
        self.assertEqual(by_id[record_b.id], "Different name B")
        self.assertFalse(by_id[unknown.id])
        self.assertFalse(record_a.employee_id)
        # No stored copy: changes to the device's name should be reflected
        # without rewriting historical raw attendance evidence.
        user_a.name = "Corrected device name"
        self.env.invalidate_all()
        self.assertEqual(record_a.device_user_name, "Corrected device name")
        self.assertEqual(record_a.device_id_num, "1008")
        self.assertEqual(record_a.punch_type, "0")

    def test_group_by_name_uses_exact_device_user_identity(self):
        user_a = self.User.create({
            "device_id": self.device_a.id, "pin": "2200", "name": "SAME NAME",
        })
        user_b = self.User.create({
            "device_id": self.device_b.id, "pin": "2200", "name": "SAME NAME",
        })
        log_a = self._raw(self.device_a, "2200", "2026-10-12 09:00:00")
        log_b = self._raw(self.device_b, "2200", "2026-10-12 09:01:00")
        self.assertEqual(log_a.device_user_id, user_a)
        self.assertEqual(log_b.device_user_id, user_b)
        self.assertFalse(log_a.employee_id)
        self.assertFalse(log_b.employee_id)
        groups = self.Raw.read_group(
            [("id", "in", (log_a | log_b).ids)],
            ["device_user_id"], ["device_user_id"], lazy=False,
        )
        group_ids = {g["device_user_id"][0] for g in groups if g["device_user_id"]}
        self.assertEqual(group_ids, {user_a.id, user_b.id})
        self.assertIn("SAME NAME", user_a.display_name)
        self.assertIn(self.device_a.serial_number, user_a.display_name)

    def test_importing_late_user_links_old_unmapped_punch_for_grouping_only(self):
        old = self._raw(self.device_a, "2300", "2026-10-12 10:00:00")
        self.assertFalse(old.device_user_id)
        self.assertFalse(old.employee_id)
        user = self.User.create({
            "device_id": self.device_a.id, "pin": "2300", "name": "LATE PROFILE",
        })
        old.invalidate_recordset(["device_user_id"])
        self.assertEqual(old.device_user_id, user)
        self.assertEqual(old.device_user_name, "LATE PROFILE")
        self.assertFalse(old.employee_id)

    def test_search_view_has_database_groupable_device_user(self):
        group_field = self.Raw._fields["device_user_id"]
        self.assertTrue(group_field.store)
        search_view = self.env.ref(
            "tam_hr_zk_attendance.machine_attendance_view_search"
        ).arch_db
        self.assertIn('name="group_device_user"', search_view)
        self.assertIn('"device_user_id"', search_view.replace("&quot;", '"'))
