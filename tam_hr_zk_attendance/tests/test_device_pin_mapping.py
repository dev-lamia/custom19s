# -*- coding: utf-8 -*-
import importlib.util
from datetime import datetime
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import OrderedSet

from ..controllers import zk_push
from ..models.zk_hardening import _zk_supported_checkout_mode


class TestDevicePinMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device_a = cls.env["zk.device"].create({"name": "Bahrain Entrance", "serial_number": "TEST-A", "is_approved": True, "allow_push": True, "tz": "Asia/Bahrain"})
        cls.device_b = cls.env["zk.device"].create({"name": "Dubai Entrance", "serial_number": "TEST-B", "is_approved": True, "allow_push": True, "tz": "Asia/Dubai"})
        cls.device_c = cls.env["zk.device"].create({"name": "Unmapped Entrance", "serial_number": "TEST-C", "is_approved": True, "allow_push": True, "tz": "UTC"})
        cls.employee_a = cls.env["hr.employee"].create({"name": "Employee A", "device_id_num": "2"})
        cls.employee_b = cls.env["hr.employee"].create({"name": "Employee B"})

    def test_employee_id_alias_is_available_on_private_and_public_models(self):
        self.employee_b.write({"device_user_id": "EMP-2010"})
        self.assertEqual(self.employee_b.device_id_num, "EMP-2010")
        public_employee = self.env["hr.employee.public"].browse(self.employee_b.id)
        self.assertEqual(public_employee.device_user_id, "EMP-2010")

    def test_biometric_employee_metadata_is_not_exposed_to_public_profiles(self):
        private_fields = self.env["hr.employee"]._fields
        public_fields = self.env["hr.employee.public"]._fields
        self.assertEqual(private_fields["device_id_num"].groups, "hr.group_hr_user")
        self.assertEqual(private_fields["device_user_id"].groups, "hr.group_hr_user")
        self.assertEqual(private_fields["biometric_device_name"].groups, "hr.group_hr_user")
        self.assertIn("device_id_num", public_fields)
        self.assertEqual(
            public_fields["device_user_id"].groups,
            "tam_hr_zk_attendance.group_biometric_manager",
        )

    def test_public_employee_id_is_visible_only_to_its_employee(self):
        user = self.env["res.users"].create({
            "name": "Employee User",
            "login": "employee.user@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.employee_b.write({"device_id_num": "EMP-2010", "user_id": user.id})
        Public = self.env["hr.employee.public"].with_user(user)
        self.assertEqual(Public.browse(self.employee_b.id).device_id_num, "EMP-2010")
        self.assertFalse(Public.browse(self.employee_a.id).device_id_num)

    def test_public_employee_proxy_labels_are_unique_and_views_stay_familiar(self):
        user_fields = self.env["zk.device.user"]._fields
        wizard_fields = self.env["zk.attendance.mapping.wizard"]._fields
        self.assertEqual(user_fields["employee_id"].string, "Mapped Employee")
        self.assertEqual(user_fields["employee_public_id"].string, "Employee (Public Directory)")
        self.assertNotEqual(user_fields["employee_id"].string, user_fields["employee_public_id"].string)
        self.assertEqual(wizard_fields["employee_id"].string, "Current Employee")
        self.assertEqual(wizard_fields["employee_public_id"].string, "Current Employee (Public Directory)")
        self.assertNotEqual(wizard_fields["employee_id"].string, wizard_fields["employee_public_id"].string)
        device_form = self.env.ref("tam_hr_zk_attendance.zk_device_user_view_form").arch_db
        wizard_form = self.env.ref("tam_hr_zk_attendance.zk_attendance_mapping_wizard_view_form").arch_db
        self.assertIn('name="employee_public_id" string="Mapped Employee"', device_form)
        self.assertIn('name="employee_public_id" string="Current Employee"', wizard_form)

    def test_same_pin_is_independent_per_device(self):
        User = self.env["zk.device.user"]
        first = User.create({"device_id": self.device_a.id, "pin": "2", "name": "A", "employee_id": self.employee_a.id})
        second = User.create({"device_id": self.device_b.id, "pin": "2", "name": "B", "employee_id": self.employee_b.id})
        self.assertEqual(first.employee_id, self.employee_a)
        self.assertEqual(second.employee_id, self.employee_b)

    def test_adms_registration_company_is_available(self):
        self.assertTrue(self.env["zk.device"]._adms_registration_company())

    def test_pull_never_uses_legacy_employee_pin(self):
        user = self.env["zk.device.user"].upsert_from_adms(self.device_c, {"pin": "2", "name": "Different person"})
        self.assertFalse(user.employee_id)
        self.assertEqual(user.device_id, self.device_c)

    def test_unknown_device_pin_stays_unmapped(self):
        raw = self.env["zk.machine.attendance"].create({
            "device_id": self.device_c.id, "device_id_num": "2", "punch_type": "0",
            "punching_time": fields.Datetime.to_string(datetime(2026, 10, 7, 8, 0, 0)),
        })
        self.assertFalse(raw.employee_id)

    def test_correction_changes_only_selected_device_pin(self):
        User = self.env["zk.device.user"]
        user_a = User.search([("device_id", "=", self.device_a.id), ("pin", "=", "2")], limit=1)
        user_b = User.search([("device_id", "=", self.device_b.id), ("pin", "=", "2")], limit=1)
        if not user_a:
            user_a = User.create({"device_id": self.device_a.id, "pin": "2", "employee_id": self.employee_a.id})
        if not user_b:
            user_b = User.create({"device_id": self.device_b.id, "pin": "2", "employee_id": self.employee_a.id})
        raw = self.env["zk.machine.attendance"].create({
            "device_id": self.device_b.id, "device_id_num": "2", "employee_id": self.employee_a.id, "punch_type": "0",
            "punching_time": fields.Datetime.to_string(datetime(2026, 10, 7, 9, 0, 0)),
        })
        wizard = self.env["zk.attendance.mapping.wizard"].create({
            "device_user_id": user_b.id,
            "correct_employee_public_id": self.employee_b.id,
            "date_from": "2026-10-07", "date_to": "2026-10-07", "mode": "correct_raw",
        })
        wizard.action_correct_raw()
        self.assertEqual(user_b.employee_id, self.employee_b)
        self.assertEqual(user_a.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_b)

    def test_verified_fingerprint_is_cached_in_generic_private_store(self):
        Template = self.env["zk.device.biometric.template"]
        first = Template.upsert_from_adms(self.device_a, {
            "pin": "2", "biometric_type": "fingerprint", "template_index": 1,
            "template_size": 4, "template": "VEVTVA==", "valid": 1,
        })
        second = Template.upsert_from_adms(self.device_a, {
            "pin": "2", "biometric_type": "fingerprint", "template_index": 1,
            "template_size": 4, "template": "VEVTVA==", "valid": 1,
        })
        self.assertEqual(first, second)
        self.assertEqual(Template.search_count([("device_id", "=", self.device_a.id), ("pin", "=", "2")]), 1)

    def test_same_device_transfer_and_target_conflict_are_blocked(self):
        User = self.env["zk.device.user"]
        source = User.create({"device_id": self.device_c.id, "pin": "8", "name": "Source"})
        with self.assertRaises(UserError):
            source._queue_transfer_to_device(self.device_c)
        User.create({"device_id": self.device_b.id, "pin": "8", "name": "Existing target user"})
        with self.assertRaises(UserError):
            source._queue_transfer_to_device(self.device_b)


    def test_dashboard_actions_open_exact_filtered_results(self):
        dashboard = self.env.ref("tam_hr_zk_attendance.zk_biometric_dashboard_record")
        today_action = dashboard.action_open_today()
        self.assertEqual(today_action["context"], {"search_default_today": 1})
        self.assertEqual(today_action["domain"][0][0], "punching_time")
        online_action = dashboard.action_open_online_devices()
        self.assertEqual(online_action["context"], {"search_default_online": 1})
        self.assertEqual(online_action["domain"][0][:2], ("last_seen", ">="))
        offline_action = dashboard.action_open_offline_devices()
        self.assertEqual(offline_action["context"], {"search_default_offline": 1})
        self.assertEqual(offline_action["domain"][0], "|")
        mapped_action = dashboard.action_open_device_users()
        self.assertEqual(mapped_action["context"], {"search_default_mapped": 1})
        self.assertEqual(mapped_action["domain"], [("employee_id", "!=", False)])

    def test_attendance_search_uses_native_date_tokens(self):
        arch = self.env.ref("tam_hr_zk_attendance.machine_attendance_view_search").arch_db
        self.assertIn("today +1d", arch)
        self.assertIn("today -1d", arch)
        self.assertNotIn("tomorrow", arch)

    def test_connection_status_search_domains_are_available(self):
        Device = self.env["zk.device"]
        self.assertEqual(Device._search_connection_status("=", "online")[0][0], "last_seen")
        self.assertEqual(Device._search_connection_status("=", "offline")[0], "|")
        self.assertEqual(
            Device._search_connection_status("=", OrderedSet(["online"]))[0][0],
            "last_seen",
        )
        self.assertEqual(
            Device._search_connection_status("=", OrderedSet(["offline"]))[0],
            "|",
        )
        # Reproduce the value type passed by the Odoo 19 domain optimizer.
        Device.search([("connection_status", "=", OrderedSet(["online"]))])
        Device.search([("connection_status", "=", OrderedSet(["offline"]))])


    def test_mapping_actions_open_only_their_workflow(self):
        user = self.env["zk.device.user"].create({
            "device_id": self.device_a.id, "pin": "901", "name": "Workflow test", "employee_id": self.employee_a.id,
        })
        map_action = user.action_open_mapping_wizard()
        self.assertEqual(map_action["context"]["default_workflow"], "map")
        self.assertEqual(map_action["context"]["default_mapping_mode"], "map_only")
        correct_action = user.action_open_correction_wizard()
        self.assertEqual(correct_action["context"]["default_workflow"], "correct")
        self.assertEqual(correct_action["context"]["default_correction_mode"], "correct_raw")

    def _new_correction(self, pin="902", employee=None, punches=1, **values):
        """Fixture for corrections to an exact device + PIN and UTC local day."""
        user = self.env["zk.device.user"].create({
            "device_id": self.device_c.id, "pin": pin, "name": "Correction fixture",
            "employee_id": (employee or self.employee_a).id,
        })
        raw = self.env["zk.machine.attendance"]
        if punches:
            raw = raw.create({
                "device_id": self.device_c.id, "device_id_num": pin,
                "employee_id": (employee or self.employee_a).id,
                "punch_type": "0", "punching_time": "2026-10-07 10:00:00",
            })
        fields = {
            "device_user_id": user.id, "workflow": "correct",
            "correct_employee_public_id": self.employee_b.id,
            "date_from": "2026-10-07", "date_to": "2026-10-07",
            "correction_mode": "correct_raw", "mode": "correct_raw",
        }
        fields.update(values)
        wizard = self.env["zk.attendance.mapping.wizard"].create(fields)
        return user, raw, wizard

    def test_correction_only_offers_public_existing_employee(self):
        Wizard = self.env["zk.attendance.mapping.wizard"]
        self.assertEqual(Wizard._fields["correct_employee_public_id"].comodel_name, "hr.employee.public")
        self.assertNotIn("new_employee_name", Wizard._fields)
        self.assertNotIn("new_employee_id", Wizard._fields)
        self.assertNotIn("correction_target", Wizard._fields)
        view = self.env.ref("tam_hr_zk_attendance.zk_attendance_mapping_wizard_view_form").arch_db
        self.assertIn('name="device_user_id" invisible="1"', view)
        self.assertIn("'no_create': True", view)
        self.assertIn("'no_create_edit': True", view)
        self.assertIn("'allowed_company_ids': eligible_employee_company_ids", view)
        self.assertNotIn("new_employee_name", view)
        self.assertNotIn("correction_target", view)

    def test_existing_employee_picker_uses_public_employee_directory(self):
        user, raw, wizard = self._new_correction(pin="903")
        company = wizard.company_id
        self.assertEqual(company, self.device_c.company_id)
        public_employee = self.env["hr.employee.public"].with_company(company).search([
            ("id", "=", self.employee_b.id), ("company_id", "=", company.id),
        ], limit=1)
        self.assertTrue(public_employee)
        wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_b)
        self.assertEqual(raw.employee_id, self.employee_b)

    def test_correction_rejects_same_employee_without_changes(self):
        user, raw, wizard = self._new_correction(pin="904", correct_employee_public_id=self.employee_a.id)
        with self.assertRaises(ValidationError):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)

    def test_correction_rejects_empty_date_range_without_changes(self):
        user, raw, wizard = self._new_correction(pin="905", date_from=False)
        with self.assertRaises(ValidationError):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)

    def test_correction_rejects_reversed_dates_without_changes(self):
        user, raw, wizard = self._new_correction(pin="906", date_from="2026-10-08")
        with self.assertRaises(ValidationError):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)

    def test_correction_rejects_no_matching_raw_punches(self):
        user, _, wizard = self._new_correction(pin="907", punches=0)
        with self.assertRaises(ValidationError):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)

    def test_correction_rejects_missing_correct_employee(self):
        user, raw, wizard = self._new_correction(pin="908", correct_employee_public_id=False)
        with self.assertRaises(ValidationError):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)

    def test_correction_rejects_employee_in_unauthorized_company(self):
        foreign_company = self.env["res.company"].create({"name": "Foreign unauthorized company"})
        foreign_employee = self.env["hr.employee"].sudo().create({
            "name": "Non-visible employee", "company_id": foreign_company.id,
        })
        user, raw, wizard = self._new_correction(pin="909", correct_employee_public_id=foreign_employee.id)
        with self.assertRaises((ValidationError, AccessError)):
            wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)

    def test_manager_without_private_hr_access_can_correct_using_public_picker(self):
        user, raw, _ = self._new_correction(pin="911")
        manager = self.env["res.users"].create({
            "name": "Biometric test manager", "login": "biometric_manager_test",
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("tam_hr_zk_attendance.group_biometric_manager").id,
            ])],
        })
        self.assertFalse(manager.has_group("hr.group_hr_user"))
        public = self.env["hr.employee.public"].with_user(manager).search([
            ("id", "=", self.employee_b.id),
            ("company_id", "=", user.company_id.id),
        ], limit=1)
        self.assertTrue(public)
        wizard = self.env["zk.attendance.mapping.wizard"].with_user(manager).create({
            "device_user_id": user.id, "workflow": "correct",
            "correct_employee_public_id": public.id,
            "date_from": "2026-10-07", "date_to": "2026-10-07",
            "correction_mode": "correct_raw", "mode": "correct_raw",
        })
        wizard.action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_b)
        self.assertEqual(raw.employee_id, self.employee_b)

    def _cross_company_fixture(self):
        """Device in A and employee in B; both belong to the manager's companies."""
        foreign_company = self.env["res.company"].create({"name": "Other biometric location company"})
        employee = self.env["hr.employee"].sudo().create({
            "name": "Visiting employee", "company_id": foreign_company.id,
        })
        manager = self.env["res.users"].create({
            "name": "Cross-company biometric manager",
            "login": "zk_cross_company_manager_test",
            "company_id": self.device_a.company_id.id,
            "company_ids": [(6, 0, [self.device_a.company_id.id, foreign_company.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("tam_hr_zk_attendance.group_biometric_manager").id,
            ])],
        })
        self.assertFalse(manager.has_group("hr.group_hr_user"))
        return foreign_company, employee, manager

    def test_cross_company_employee_mapping_preserves_device_company(self):
        company_b, employee_b, manager = self._cross_company_fixture()
        user = self.env["zk.device.user"].create({
            "device_id": self.device_a.id, "pin": "CC-100", "name": "Visitor",
        })
        self.assertNotEqual(user.company_id, company_b)
        # Manager has both company permissions but only company A active.
        user.with_user(manager).with_context(
            allowed_company_ids=[self.device_a.company_id.id]
        ).write({"employee_public_id": employee_b.id})
        self.assertEqual(user.employee_id, employee_b)
        self.assertEqual(user.employee_public_id.id, employee_b.id)
        self.assertEqual(user.company_id, self.device_a.company_id)
        self.assertFalse(user.employee_id.company_id == user.company_id)
        allowed = user.with_user(manager).eligible_employee_company_ids
        self.assertIn(company_b, allowed)
        self.assertIn(self.device_a.company_id, allowed)
        # Raw attendance stays in the physical device's company.
        raw = self.env["zk.machine.attendance"].create({
            "device_id": self.device_a.id, "device_id_num": user.pin,
            "punch_type": "0", "punching_time": "2026-10-07 10:00:00",
            "employee_id": employee_b.id,
        })
        self.assertEqual(raw.employee_id, employee_b)
        self.assertEqual(raw.company_id, self.device_a.company_id)

    def test_cross_company_mapping_denied_without_employee_company_access(self):
        company_b, employee_b, _ = self._cross_company_fixture()
        manager_a = self.env["res.users"].create({
            "name": "A-only biometric manager", "login": "zk_company_a_only_test",
            "company_id": self.device_a.company_id.id,
            "company_ids": [(6, 0, [self.device_a.company_id.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("tam_hr_zk_attendance.group_biometric_manager").id,
            ])],
        })
        user = self.env["zk.device.user"].create({
            "device_id": self.device_a.id, "pin": "CC-101",
        })
        with self.assertRaises(AccessError):
            user.with_user(manager_a).write({"employee_public_id": employee_b.id})
        # The private field remains protected against direct RPC writes, too.
        with self.assertRaises(AccessError):
            user.with_user(manager_a).write({"employee_id": employee_b.id})
        self.assertFalse(user.employee_id)

    def test_cross_company_correction_uses_public_hr_and_exact_device_pin(self):
        company_b, employee_b, manager = self._cross_company_fixture()
        user, raw, wizard = self._new_correction(
            pin="CC-102", correct_employee_public_id=employee_b.id,
        )
        wizard = wizard.with_user(manager).with_context(
            allowed_company_ids=[self.device_c.company_id.id]
        )
        wizard.action_correct_raw()
        self.assertEqual(user.employee_id, employee_b)
        self.assertEqual(raw.employee_id, employee_b)
        self.assertEqual(raw.company_id, self.device_c.company_id)
        self.assertNotEqual(user.company_id, company_b)

    def test_correction_requires_device_company_permission(self):
        user, raw, wizard = self._new_correction(pin="910")
        # Test server-side guard against crafted requests, not the UI domain.
        # An unrelated normal user does not gain device management by guessing wizard IDs.
        normal_user = self.env["res.users"].create({
            "name": "Biometric outsider", "login": "biometric_outsider_test",
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            wizard.with_user(normal_user).action_correct_raw()
        self.assertEqual(user.employee_id, self.employee_a)
        self.assertEqual(raw.employee_id, self.employee_a)


class TestPrivateBiometricModelAccess(TransactionCase):
    """Explicit ACL rows must not leak biometric bytes or legacy wizards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_service_group = cls.env.ref(
            "tam_hr_zk_attendance.group_biometric_protocol_internal"
        )
        cls.operator_group = cls.env.ref("tam_hr_zk_attendance.group_biometric_user")
        cls.manager_group = cls.env.ref("tam_hr_zk_attendance.group_biometric_manager")
        cls.standard_group = cls.env.ref("base.group_user")

    def _user_with_groups(self, username, extra_groups=()):
        """The service role is deliberately NOT present on normal accounts."""
        return self.env["res.users"].create({
            "name": username,
            "login": username,
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
            "group_ids": [(6, 0, [self.standard_group.id] + list(extra_groups))],
        })

    def test_sensitive_models_have_service_only_acl_entries(self):
        access = self.env["ir.model.access"]
        for model in (
            "zk.device.biometric.template",
            "zk.device.fingerprint",
            "zk.device.user.sync.wizard",
        ):
            with self.subTest(model=model):
                records = access.search([
                    ("model_id.model", "=", model),
                    ("group_id", "=", self.internal_service_group.id),
                ])
                self.assertTrue(records, "No internal ACL entry for %s" % model)

    def test_normal_operator_manager_cannot_read_private_protocol_models(self):
        for username, groups in (
            ("zk_security_basic", []),
            ("zk_security_operator", [self.operator_group.id]),
            ("zk_security_manager", [self.manager_group.id]),
        ):
            user = self._user_with_groups(username, groups)
            self.assertNotIn(self.internal_service_group, user.group_ids)
            for model in (
                "zk.device.biometric.template",
                "zk.device.fingerprint",
                "zk.device.user.sync.wizard",
            ):
                with self.subTest(user=username, model=model):
                    with self.assertRaises(AccessError):
                        self.env[model].with_user(user).check_access("read")


    def test_post_migration_backfills_serial_after_schema_creation(self):
        device = self.env["zk.device"].create({
            "name": "LEGACY-SERIAL-MIGRATION-TEST", "serial_number": "LEGACY-SERIAL-MIGRATION-TEST",
        })
        self.env.cr.execute("UPDATE zk_device SET serial_number = NULL WHERE id = %s", (device.id,))
        migration_path = Path(__file__).parents[1] / "migrations" / "19.0.0.0.33" / "post-migration.py"
        spec = importlib.util.spec_from_file_location("zk_serial_post_migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, "19.0.0.0.33")
        device.invalidate_recordset(["serial_number"])
        self.assertEqual(device.serial_number, "LEGACY-SERIAL-MIGRATION-TEST")


class TestNextDayMissedCheckout(TransactionCase):
    """Regression: next check-in closes ONLY an older proven biometric open."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["zk.device"].create({
            "name": "Next-day fixture", "serial_number": "TEST-NEXT-DAY-CHECKOUT",
            "tz": "UTC", "is_approved": True, "allow_push": True,
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Next-day test employee"})
        cls.pin = "98123"
        cls.device_user = cls.env["zk.device.user"].create({
            "device_id": cls.device.id, "pin": cls.pin,
            "name": "Next-day user", "employee_id": cls.employee.id,
        })

    def _attendance(self, check_in, check_out=False, *, proven=True):
        values = {
            "employee_id": self.employee.id,
            "check_in": check_in,
            "check_out": check_out,
        }
        if proven:
            values.update({
                "biometric_generated": True,
                "biometric_device_id": self.device.id,
                "biometric_pin": self.pin,
            })
        return self.env["hr.attendance"].sudo().create(values)

    def _raw(self, check_in):
        return self.env["zk.machine.attendance"].sudo().create({
            "device_id": self.device.id, "device_id_num": self.pin,
            "employee_id": self.employee.id, "punch_type": "0",
            "punching_time": check_in,
        })

    def _rebuild(self, start, end):
        wizard = self.env["zk.attendance.mapping.wizard"].create({
            "device_user_id": self.device_user.id,
            "date_from": start, "date_to": end,
        })
        return wizard._rebuild_attendance(self.employee)

    def test_live_device_batch_order_and_zero_hours(self):
        # A single out-of-order POST carries the next-day check-in FIRST.
        controller = zk_push.ZKPushController()
        payload = (
            f"{self.pin}\t2026-09-24 08:30:00\t0\t1\n"
            f"{self.pin}\t2026-09-23 07:37:28\t0\t1\n"
        )
        with patch.object(zk_push, "request", SimpleNamespace(env=self.env)):
            created, skipped, unmapped = controller._store_attendance_payload(self.device, payload)
        self.assertEqual((created, skipped, unmapped), (2, 0, 0))
        attendances = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", self.employee.id),
        ], order="check_in asc")
        self.assertEqual(len(attendances), 2)
        self.assertEqual(attendances[0].check_out, attendances[0].check_in)
        self.assertEqual(attendances[0].worked_hours, 0.0)
        self.assertEqual(attendances[1].check_in, attendances[1].check_out)

    def test_historical_rebuild_uses_chronological_days_and_is_idempotent(self):
        self._raw("2026-09-24 08:30:00")
        self._raw("2026-09-23 07:37:28")
        self.assertEqual(self._rebuild("2026-09-23", "2026-09-24"), (2, 0))
        rows = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", self.employee.id),
        ], order="check_in asc")
        self.assertEqual(rows[0].check_in, rows[0].check_out)
        self.assertEqual(rows[0].worked_hours, 0.0)
        self.assertEqual(rows[1].check_in, rows[1].check_out)
        self.assertEqual(self._rebuild("2026-09-23", "2026-09-24"), (0, 0))
        self.assertEqual(rows[0].check_in, rows[0].check_out)

    def test_rebuild_closes_existing_previous_day_outside_selection(self):
        old = self._attendance("2026-09-23 07:37:28")
        self._raw("2026-09-24 08:30:00")
        self.assertEqual(self._rebuild("2026-09-24", "2026-09-24"), (1, 0))
        self.assertEqual(old.check_in, old.check_out)
        self.assertEqual(old.worked_hours, 0.0)

    def test_real_checkout_wins_after_zero_hour_autoclose(self):
        old = self._attendance("2026-09-23 07:37:28")
        self._raw("2026-09-23 07:37:28")
        self._raw("2026-09-24 08:30:00")
        self._rebuild("2026-09-24", "2026-09-24")
        self.assertEqual(old.check_in, old.check_out)
        # When a genuine second punch is subsequently received, it replaces
        # the earlier zero-hour placeholder (and never crosses into day two).
        self._raw("2026-09-23 17:40:00")
        self._rebuild("2026-09-23", "2026-09-23")
        self.assertEqual(fields.Datetime.to_string(old.check_out), "2026-09-23 17:40:00")

    def test_manual_open_is_never_closed_and_blocks_rebuild(self):
        old = self._attendance("2026-09-23 07:37:28", proven=False)
        self._raw("2026-09-24 08:30:00")
        with self.assertRaisesRegex(ValidationError, "without verified biometric provenance"):
            self._rebuild("2026-09-24", "2026-09-24")
        self.assertFalse(old.check_out)

    def test_native_mode_detection_auto_then_manual_then_missing(self):
        class NativeSelection:
            def __init__(self, choices):
                self.choices = choices
            def get_values(self, env):
                return self.choices
        self.assertEqual(_zk_supported_checkout_mode(
            NativeSelection(["manual", "auto_check_out"]), self.env
        ), "auto_check_out")
        self.assertEqual(_zk_supported_checkout_mode(
            NativeSelection(["manual", "technical"]), self.env
        ), "manual")
        self.assertFalse(_zk_supported_checkout_mode(None, self.env))
        self.assertFalse(_zk_supported_checkout_mode(NativeSelection(["technical"]), self.env))
        native = self.env["hr.attendance"].sudo()
        if "out_mode" in native._fields:
            mode = _zk_supported_checkout_mode(native._fields["out_mode"], self.env)
            previous = self._attendance("2026-09-23 07:37:28")
            values = native._zk_zero_hour_checkout_values(previous)
            self.assertEqual(values.get("out_mode", False), mode)
