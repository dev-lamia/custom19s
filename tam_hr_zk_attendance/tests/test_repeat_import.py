# -*- coding: utf-8 -*-
"""Regression tests for re-imports and reconciled historical attendance."""
from types import SimpleNamespace
from datetime import date
import pytz
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

from ..controllers import zk_push


class TestRepeatAttendanceImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["zk.device"].create({
            "name": "Repeat import fixture",
            "serial_number": "TEST-REIMPORT-IDEMPOTENCY-2026",
            "tz": "UTC", "is_approved": True, "allow_push": True,
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Repeat import employee"})
        cls.pin = "97211"
        cls.device_user = cls.env["zk.device.user"].create({
            "device_id": cls.device.id, "pin": cls.pin,
            "name": "Repeat import employee", "employee_id": cls.employee.id,
        })

    def _push(self, *timestamps_and_types):
        rows = [
            "%s\t%s\t%s\t1" % (self.pin, date_time, typ)
            for date_time, typ in timestamps_and_types
        ]
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            return zk_push.ZKPushController()._store_attendance_payload(
                self.device, "\n".join(rows)
            )

    def _raw(self):
        return self.env["zk.machine.attendance"].sudo().search([
            ("device_id", "=", self.device.id),
            ("device_id_num", "=", self.pin),
        ])

    def _hr(self):
        return self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", self.employee.id),
        ], order="check_in asc")

    def test_second_pull_creates_no_raw_or_hr_duplicate(self):
        punch_pair = (("2026-07-16 08:00:00", "0"), ("2026-07-16 17:00:00", "1"))
        self.assertEqual(self._push(*punch_pair), (2, 0, 0))
        initial_ids = self._raw().ids
        hr_ids = self._hr().ids
        self.assertEqual(self._push(*punch_pair), (0, 2, 0))
        self.assertEqual(self._raw().ids, initial_ids)
        self.assertEqual(self._hr().ids, hr_ids)
        self.assertEqual(self._hr().worked_hours, 9.0)

    def test_repeat_plus_new_punch_only_creates_new_raw(self):
        self._push(("2026-07-16 08:00:00", "0"))
        self.assertEqual(self._push(
            ("2026-07-16 08:00:00", "0"),
            ("2026-07-16 17:00:00", "1"),
        ), (1, 1, 0))
        self.assertEqual(len(self._raw()), 2)
        self.assertEqual(len(self._hr()), 1)
        self.assertEqual(fields.Datetime.to_string(self._hr().check_out), "2026-07-16 17:00:00")

    def test_historical_unmapped_raw_is_linked_not_duplicated(self):
        Log = self.env["zk.machine.attendance"].sudo()
        self.device_user.employee_id = False
        existing = Log.create({
            "device_id": self.device.id, "device_id_num": self.pin,
            "punch_type": "0", "punching_time": "2026-07-17 08:00:00",
        })
        # Simulate historical evidence created before the event-key column.
        self.env.cr.execute(
            "UPDATE zk_machine_attendance SET source_event_key=NULL WHERE id=%s",
            (existing.id,),
        )
        existing.invalidate_recordset(["source_event_key"])
        self.device_user.employee_id = self.employee
        self.assertEqual(self._push(("2026-07-17 08:00:00", "0")), (0, 1, 0))
        self.assertEqual(self._raw().ids, existing.ids)
        self.assertEqual(existing.employee_id, self.employee)
        self.assertFalse(existing.source_event_key)  # no historical backfill
        self.assertEqual(len(self._hr()), 1)

    def test_existing_manual_hr_records_are_not_duplicated_or_relabelled(self):
        original = self.env["hr.attendance"].sudo().create({
            "employee_id": self.employee.id,
            "check_in": "2026-07-16 04:59:40",
            "check_out": "2026-07-16 14:12:35",
        })
        pair = (("2026-07-16 05:19:22", "0"), ("2026-07-16 13:50:00", "1"))
        self.assertEqual(self._push(*pair), (2, 0, 0))
        self.assertEqual(self._push(*pair), (0, 2, 0))
        self.assertEqual(self._hr().ids, original.ids)
        self.assertFalse(original.biometric_generated)
        self.assertEqual(len(self._raw()), 2)

    def test_exact_matching_unproven_hr_is_an_idempotent_noop(self):
        """Production case: September 14/15 already match raw events to the second."""
        Attendance = self.env["hr.attendance"].sudo()
        record_14 = Attendance.create({
            "employee_id": self.employee.id,
            "check_in": "2026-09-14 05:10:40",
            "check_out": "2026-09-14 14:08:50",
        })
        record_15 = Attendance.create({
            "employee_id": self.employee.id,
            "check_in": "2026-09-15 05:05:25",
            "check_out": "2026-09-15 14:36:57",
        })
        source_events = (
            ("2026-09-14 05:10:40", "0"),
            ("2026-09-14 07:02:42", "1"),
            ("2026-09-14 10:34:45", "5"),
            ("2026-09-14 13:31:08", "4"),
            ("2026-09-14 14:08:50", "4"),
            ("2026-09-15 05:05:25", "0"),
            ("2026-09-15 08:16:54", "1"),
            ("2026-09-15 10:38:17", "5"),
            ("2026-09-15 11:23:36", "5"),
            ("2026-09-15 13:59:17", "4"),
            ("2026-09-15 14:36:57", "4"),
        )
        self.assertEqual(self._push(*source_events), (11, 0, 0))
        self.assertEqual(self._push(*source_events), (0, 11, 0))
        self.assertEqual(self._hr().ids, [record_14.id, record_15.id])
        self.assertFalse(record_14.biometric_generated)
        self.assertFalse(record_15.biometric_generated)
        for day, check_in, check_out in [
            (14, record_14.check_in, record_14.check_out),
            (15, record_15.check_in, record_15.check_out),
        ]:
            logs = self._raw().filtered(
                lambda log: log.punching_time.date() == date(2026, 9, day)
            ).sorted("punching_time")
            self.assertEqual(self.env["hr.attendance"].sudo()._zk_sync_local_day(
                self.employee.id, self.device, self.pin, logs, pytz.UTC,
            ), "unchanged")
            self.assertEqual(logs[0].punching_time, check_in)
            self.assertEqual(logs[-1].punching_time, check_out)

    def test_different_unproven_hr_remains_a_conflict(self):
        original = self.env["hr.attendance"].sudo().create({
            "employee_id": self.employee.id,
            "check_in": "2026-09-14 05:10:40",
            "check_out": "2026-09-14 14:00:00",
        })
        self._push(("2026-09-14 05:10:40", "0"), ("2026-09-14 14:08:50", "4"))
        self.assertEqual(self._hr().ids, original.ids)
        self.assertEqual(fields.Datetime.to_string(original.check_out), "2026-09-14 14:00:00")
        self.assertEqual(self.env["hr.attendance"].sudo()._zk_sync_local_day(
            self.employee.id, self.device, self.pin,
            self._raw().sorted("punching_time"), pytz.UTC,
        ), "conflict")

    def test_existing_proven_biometric_is_reused_across_devices(self):
        """A second source updates the employee day without creating a second row."""
        from ..models import zk_hardening

        another = self.env["zk.device"].create({
            "name": "Second source", "serial_number": "TEST-SECOND-SOURCE-2026",
            "tz": "UTC", "is_approved": True,
        })
        existing = self.env["hr.attendance"].sudo().create({
            "employee_id": self.employee.id,
            "check_in": "2026-07-16 08:00:00",
            "check_out": "2026-07-16 17:00:00",
            "biometric_generated": True,
            "biometric_device_id": another.id,
            "biometric_pin": "88",
        })
        with patch.object(zk_hardening, "_logger") as log:
            self.assertEqual(self._push(("2026-07-16 09:00:00", "0")), (1, 0, 0))
        self.assertEqual(self._hr().ids, existing.ids)
        self.assertEqual(len(self._raw()), 1)
        # A partial push must not shrink older proven attendance history.
        self.assertEqual(fields.Datetime.to_string(existing.check_in), "2026-07-16 08:00:00")
        self.assertEqual(fields.Datetime.to_string(existing.check_out), "2026-07-16 17:00:00")
        self.assertFalse(any("ZK HR sync conflict" in str(call)
                             for call in log.warning.call_args_list))

    def test_older_manual_open_kept_and_reported_for_review(self):
        """No auto-closure, raw event retained, no full ERROR traceback."""
        original = self.env["hr.attendance"].sudo().create({
            "employee_id": self.employee.id,
            "check_in": "2026-07-15 04:00:00",
        })
        with patch.object(zk_push, "_logger") as log:
            self.assertEqual(self._push(("2026-07-16 08:00:00", "0")), (1, 0, 0))
        self.assertEqual(self._hr().ids, original.ids)
        self.assertFalse(original.check_out)
        self.assertEqual(len(self._raw()), 1)
        self.assertTrue(any("requires manual review" in str(call)
                            for call in log.warning.call_args_list))
        self.assertFalse(log.exception.called)

    def test_single_completed_day_stays_zero_hour_after_reimport(self):
        self.assertEqual(self._push(("2026-07-16 08:00:00", "0")), (1, 0, 0))
        attendance = self._hr()
        self.assertEqual(attendance.check_out, attendance.check_in)
        self.assertEqual(attendance.worked_hours, 0.0)
        self.assertEqual(self._push(("2026-07-16 08:00:00", "0")), (0, 1, 0))
        self.assertEqual(self._hr().ids, attendance.ids)
        self.assertEqual(self._hr().worked_hours, 0.0)

    def test_first_last_rule_uses_even_two_checkin_punches(self):
        self._push(("2026-07-16 08:00:00", "0"), ("2026-07-16 08:01:00", "0"))
        attendance = self._hr()
        self.assertEqual(fields.Datetime.to_string(attendance.check_out), "2026-07-16 08:01:00")
        self._push(("2026-07-16 17:00:00", "1"))
        self.assertEqual(self._hr().ids, attendance.ids)
        self.assertEqual(fields.Datetime.to_string(attendance.check_out), "2026-07-16 17:00:00")

    def test_older_punch_expands_first_last_interval(self):
        self._push(("2026-07-16 09:00:00", "0"))
        attendance = self._hr()
        self._push(("2026-07-16 08:58:00", "0"))
        self.assertEqual(self._hr().ids, attendance.ids)
        self.assertEqual(fields.Datetime.to_string(attendance.check_in), "2026-07-16 08:58:00")
        self.assertEqual(fields.Datetime.to_string(attendance.check_out), "2026-07-16 09:00:00")

    def test_repeat_pull_does_not_reassign_a_confirmed_old_mapping(self):
        other = self.env["hr.employee"].create({"name": "Different employee"})
        self._push(("2026-07-16 08:00:00", "0"))
        event = self._raw()
        self.device_user.employee_id = other
        self.assertEqual(self._push(("2026-07-16 08:00:00", "0")), (0, 1, 0))
        self.assertEqual(event.employee_id, self.employee)
        self.assertEqual(len(self._hr()), 1)
        self.assertFalse(self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", other.id)
        ]))


    def test_different_pins_on_different_devices_merge_one_employee_day(self):
        device_b = self.env["zk.device"].create({
            "name": "Cross device", "serial_number": "TEST-MERGE-DIFF-PINS-2026",
            "tz": "UTC", "is_approved": True, "allow_push": True,
        })
        pin_b = "55002"
        self.env["zk.device.user"].create({
            "device_id": device_b.id, "pin": pin_b, "employee_id": self.employee.id,
            "name": "One person, another PIN",
        })
        self._push(("2026-07-16 08:00:00", "0"))
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            result = zk_push.ZKPushController()._store_attendance_payload(
                device_b, "%s\t2026-07-16 18:20:00\t4\t1" % pin_b,
            )
        self.assertEqual(result, (1, 0, 0))
        records = self._hr()
        self.assertEqual(len(records), 1)
        self.assertEqual(fields.Datetime.to_string(records.check_in), "2026-07-16 08:00:00")
        self.assertEqual(fields.Datetime.to_string(records.check_out), "2026-07-16 18:20:00")
        self.assertEqual(len(self.env["zk.machine.attendance"].sudo().search([
            ("employee_id", "=", self.employee.id),
        ])), 2)

    def test_same_pin_different_devices_do_not_merge_different_employees(self):
        employee_b = self.env["hr.employee"].create({"name": "Another PIN owner"})
        device_b = self.env["zk.device"].create({
            "name": "Duplicate PIN different user", "serial_number": "TEST-PIN-IS-LOCAL-2026",
            "tz": "UTC", "is_approved": True, "allow_push": True,
        })
        self.env["zk.device.user"].create({
            "device_id": device_b.id, "pin": self.pin,
            "employee_id": employee_b.id, "name": "Another PIN owner",
        })
        self._push(("2026-07-16 08:00:00", "0"))
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            zk_push.ZKPushController()._store_attendance_payload(
                device_b, "%s\t2026-07-16 09:00:00\t0\t1" % self.pin,
            )
        self.assertEqual(len(self._hr()), 1)
        self.assertEqual(self.env["hr.attendance"].sudo().search_count([
            ("employee_id", "=", employee_b.id),
        ]), 1)

    def test_existing_duplicate_hr_day_is_preserved_not_cleaned(self):
        Att = self.env["hr.attendance"].sudo()
        first = Att.create({
            "employee_id": self.employee.id, "check_in": "2026-07-16 08:00:00",
            "check_out": "2026-07-16 10:00:00", "biometric_generated": True,
            "biometric_device_id": self.device.id, "biometric_pin": self.pin,
        })
        second = Att.create({
            "employee_id": self.employee.id, "check_in": "2026-07-16 11:00:00",
            "check_out": "2026-07-16 12:00:00", "biometric_generated": True,
            "biometric_device_id": self.device.id, "biometric_pin": self.pin,
        })
        self._push(("2026-07-16 07:00:00", "0"), ("2026-07-16 17:00:00", "4"))
        self.assertEqual(self._hr().ids, [first.id, second.id])
        self.assertEqual(fields.Datetime.to_string(first.check_in), "2026-07-16 08:00:00")
        self.assertEqual(fields.Datetime.to_string(second.check_out), "2026-07-16 12:00:00")


class TestClassicAdminTransfer(TransactionCase):
    def test_classic_source_admin_is_enrolled_as_normal_with_ordered_templates(self):
        source = self.env["zk.device"].create({
            "name": "Classic source admin", "serial_number": "TEST-ADMIN-SOURCE-CLASSIC",
            "is_approved": True,
        })
        target = self.env["zk.device"].create({
            "name": "Classic normal target", "serial_number": "TEST-NORMAL-TARGET-CLASSIC",
            "is_approved": True,
            "last_user_sync_at": fields.Datetime.now(),
        })
        admin = self.env["zk.device.user"].create({
            "device_id": source.id, "pin": "700", "name": "Transferred Admin",
            "privilege": 14, "password": "do-not-transfer", "card": "1234567",
            "group_id": "9",
        })
        admin._queue_transfer_to_device(target)
        cmds = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id),
        ], order="id asc")
        self.assertEqual(len(cmds), 2)  # Normal profile + dependent verification.
        self.assertIn("Pri=0", cmds[0].command)
        self.assertIn("Grp=1", cmds[0].command)
        self.assertNotIn("do-not-transfer", cmds[0].command)
        self.assertNotIn("1234567", cmds[0].command)
        self.assertEqual(cmds[1].command, "DATA QUERY USERINFO PIN=700")
        self.assertEqual(cmds[1].depends_on_id, cmds[0])
