# -*- coding: utf-8 -*-
"""Cross-device mapping provenance and wizard navigation regression tests."""
from odoo.tests.common import TransactionCase


class TestTransferAutoMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = cls.env["zk.device"].create({
            "name": "Source terminal", "serial_number": "TEST-XFER-SOURCE-45",
            "is_approved": True, "tz": "UTC",
        })
        cls.target = cls.env["zk.device"].create({
            "name": "Target terminal", "serial_number": "TEST-XFER-TARGET-45",
            "is_approved": True, "tz": "UTC",
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Transfer Test Employee"})
        cls.original = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "pin": "7512",
            "name": "Transferred Employee", "employee_id": cls.employee.id,
        })

    def _profile(self, pin="7512", name="Transferred Employee"):
        command = self.target.queue_adms_command(
            "DATA USER PIN=%s\tName=%s\tPri=0" % (pin, name),
            "Transfer normal user profile",
        )
        command.sudo().write({
            "transfer_requested_by": self.env.user.id,
            "transfer_source_user_id": self.original.id,
            "transfer_employee_id": self.employee.id,
            "transfer_pin": pin,
            "transfer_name": name,
        })
        return command

    def _confirm(self, command):
        command.sudo().write({"state": "sent"})
        self.target.acknowledge_adms_command(command.command_id, "0")
        self.assertEqual(command.state, "done")

    def test_no_optimistic_mapping_until_ack_and_verified_user(self):
        command = self._profile()
        self.assertFalse(self.env["zk.device.user"].search([
            ("device_id", "=", self.target.id), ("pin", "=", "7512"),
        ]))
        # Device reports user before its profile-ack arrives.
        destination = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Transferred Employee", "pri": 0,
        })
        self.assertFalse(destination.employee_id)
        self._confirm(command)
        self.assertEqual(destination.employee_id, self.employee)
        # Repeated pull never overwrites the mapped employee or duplicates a row.
        second = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Transferred Employee", "pri": 0,
        })
        self.assertEqual(second, destination)
        self.assertEqual(second.employee_id, self.employee)

    def test_verified_user_arrives_after_profile_ack(self):
        command = self._profile()
        self._confirm(command)
        destination = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Transferred Employee", "pri": 0,
        })
        self.assertEqual(destination.employee_id, self.employee)

    def test_different_name_does_not_claim_employee(self):
        command = self._profile()
        self._confirm(command)
        destination = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Different Person", "pri": 0,
        })
        self.assertFalse(destination.employee_id)

    def test_existing_different_employee_is_preserved(self):
        stranger = self.env["hr.employee"].create({"name": "Existing Destination"})
        destination = self.env["zk.device.user"].create({
            "device_id": self.target.id, "pin": "7512",
            "name": "Transferred Employee", "employee_id": stranger.id,
        })
        command = self._profile()
        self._confirm(command)
        self.assertEqual(destination.employee_id, stranger)

    def test_latest_failed_profile_does_not_reuse_old_mapping(self):
        older = self._profile()
        self._confirm(older)
        newest = self._profile()
        newest.sudo().write({"state": "failed"})
        destination = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Transferred Employee", "pri": 0,
        })
        self.assertFalse(destination.employee_id)

    def test_transfer_wizard_queues_verification_and_closes(self):
        wizard = self.env["zk.device.user.transfer.wizard"].create({
            "device_user_id": self.original.id,
            "target_device_id": self.target.id,
            "confirm_transfer": True,
        })
        result = wizard.action_transfer()
        self.assertEqual(result["params"]["next"], {
            "type": "ir.actions.act_window_close",
        })
        commands = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id asc")
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[1].depends_on_id, commands[0])
        self.assertEqual(commands[0].transfer_employee_id, self.employee)

    def test_source_mapping_changed_after_queue_is_not_copied(self):
        command = self._profile()
        another = self.env["hr.employee"].create({"name": "Source Reassigned"})
        self.original.employee_id = another
        self._confirm(command)
        destination = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7512", "name": "Transferred Employee", "pri": 0,
        })
        self.assertFalse(destination.employee_id)


class TestWizardCloseAfterNotification(TransactionCase):
    def test_mapping_wizard_notification_closes_modal(self):
        action = self.env["zk.attendance.mapping.wizard"]._notification("Done", "Mapped")
        self.assertEqual(action["params"]["next"], {
            "type": "ir.actions.act_window_close",
        })

    def test_pull_wizard_returns_close_after_queuing(self):
        device = self.env["zk.device"].create({
            "name": "Wizard close test device", "serial_number": "TEST-PULL-WIZ-45",
            "is_approved": True, "tz": "UTC",
        })
        wizard = self.env["zk.attendance.pull.wizard"].create({
            "device_id": device.id,
            "date_from": "2026-09-14",
            "date_to": "2026-09-15",
            "batch_days": 7,
        })
        result = wizard.action_queue()
        self.assertEqual(result["params"]["next"], {
            "type": "ir.actions.act_window_close",
        })
        self.assertEqual(self.env["zk.device.command"].search_count([
            ("device_id", "=", device.id),
        ]), 1)


class TestAuthorizedCrossCompanyTransfer(TransactionCase):
    """Regression: secondary permitted company is selectable and transferable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({
            "name": "Second authorized terminal company (test)",
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Cross-company terminal manager (test)",
            "login": "zk_transfer_cross_company_46",
            "company_id": cls.company_a.id,
            "company_ids": [(6, 0, [cls.company_a.id, cls.company_b.id])],
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("tam_hr_zk_attendance.group_biometric_manager").id,
            ])],
        })
        cls.source = cls.env["zk.device"].create({
            "name": "CC Source Terminal", "serial_number": "TEST-XFER-CC-A-46",
            "company_id": cls.company_a.id, "is_approved": True, "tz": "UTC",
        })
        cls.target = cls.env["zk.device"].create({
            "name": "CC Target Terminal", "serial_number": "TEST-XFER-CC-B-46",
            "company_id": cls.company_b.id, "is_approved": True, "tz": "UTC",
            "last_user_sync_at": cls.env["zk.device"]._online_cutoff(),
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "CC Person", "company_id": cls.company_a.id,
        })
        cls.original = cls.env["zk.device.user"].create({
            "device_id": cls.source.id, "pin": "7646", "name": "CC Person",
            "employee_id": cls.employee.id,
        })

    def test_transfer_selector_uses_permitted_not_only_active_companies(self):
        wizard = self.env["zk.device.user.transfer.wizard"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company_a.id]).create({
            "device_user_id": self.original.id,
        })
        self.assertIn(self.company_b, wizard.permitted_device_company_ids)
        wizard.target_device_id = self.target
        self.assertIn("Classic ADMS user inventory refreshed", wizard.target_cache_status)
        xml = self.env.ref(
            "tam_hr_zk_attendance.zk_device_user_transfer_wizard_view_form"
        ).arch_db
        self.assertIn("('company_id', 'in', permitted_device_company_ids)", xml)
        self.assertIn("'allowed_company_ids': permitted_device_company_ids", xml)
        self.assertNotIn("('company_id', '=', source_company_id)", xml)

    def test_classic_cross_company_transfer_and_verified_mapping(self):
        wizard = self.env["zk.device.user.transfer.wizard"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company_a.id]).create({
            "device_user_id": self.original.id,
            "target_device_id": self.target.id,
            "confirm_transfer": True,
        })
        result = wizard.action_transfer()
        self.assertEqual(result["params"]["next"]["type"], "ir.actions.act_window_close")
        cmds = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id asc")
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0].transfer_employee_id, self.employee)
        self.assertEqual(cmds[1].depends_on_id, cmds[0])
        cmds[0].write({"state": "sent"})
        self.target.acknowledge_adms_command(cmds[0].command_id, "0")
        target_user = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7646", "name": "CC Person", "pri": 0,
        })
        self.assertEqual(target_user.employee_id, self.employee)
        self.assertEqual(target_user.company_id, self.company_b)
        self.assertEqual(self.original.company_id, self.company_a)

    def test_unauthorized_target_not_accepted_even_with_crafted_wizard(self):
        from odoo.exceptions import AccessError, UserError
        manager_a = self.env["res.users"].create({
            "name": "Only A terminal manager (test)",
            "login": "zk_transfer_only_a_46",
            "company_id": self.company_a.id,
            "company_ids": [(6, 0, [self.company_a.id])],
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("tam_hr_zk_attendance.group_biometric_manager").id,
            ])],
        })
        original = self.original.with_user(manager_a).with_context(
            allowed_company_ids=[self.company_a.id]
        )
        with self.assertRaises((UserError, AccessError)):
            original._queue_transfer_to_device(self.target)
        self.assertFalse(self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ]))

    def test_revoked_target_company_blocks_deferred_employee_mapping(self):
        cmd = self.target.queue_adms_command(
            "DATA USER PIN=7646\tName=CC Person\tPri=0", "CC profile",
        )
        cmd.sudo().write({
            "transfer_requested_by": self.manager.id,
            "transfer_source_user_id": self.original.id,
            "transfer_employee_id": self.employee.id,
            "transfer_pin": "7646", "transfer_name": "CC Person",
        })
        # Permission is removed AFTER queue and before the device ACK.
        self.manager.write({"company_ids": [(6, 0, [self.company_a.id])]})
        cmd.write({"state": "sent"})
        self.target.acknowledge_adms_command(cmd.command_id, "0")
        target_user = self.env["zk.device.user"].upsert_from_adms(self.target, {
            "pin": "7646", "name": "CC Person", "pri": 0,
        })
        self.assertFalse(target_user.employee_id)

    def test_security_push_cross_company_profile_still_gated(self):
        from odoo import fields
        source = self.env["zk.device"].create({
            "name": "CC Security Source", "serial_number": "TEST-XFER-CC-ACC-A-46",
            "company_id": self.company_a.id, "device_type": "acc",
            "is_approved": True, "tz": "UTC",
        })
        target = self.env["zk.device"].create({
            "name": "CC Security Target", "serial_number": "TEST-XFER-CC-ACC-B-46",
            "company_id": self.company_b.id, "device_type": "acc",
            "is_approved": True, "tz": "UTC",
            "last_user_sync_at": fields.Datetime.now(),
        })
        src_user = self.env["zk.device.user"].create({
            "device_id": source.id, "pin": "8465",
            "name": "CC Person", "employee_id": self.employee.id,
        })
        wizard = self.env["zk.device.user.transfer.wizard"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company_a.id]).create({
            "device_user_id": src_user.id,
            "target_device_id": target.id,
            "confirm_transfer": True,
            "transfer_mode": "profile_only",
        })
        wizard.action_transfer()
        commands = self.env["zk.device.command"].sudo().search([
            ("device_id", "=", target.id),
        ], order="id asc")
        self.assertEqual(len(commands), 2)
        self.assertIn("Privilege=0", commands[0].command)
        self.assertEqual(commands[1].depends_on_id, commands[0])
        commands[0].write({"state": "sent"})
        target.acknowledge_adms_command(commands[0].command_id, "0")
        dest = self.env["zk.device.user"].upsert_from_adms(target, {
            "pin": "8465", "name": "CC Person", "pri": 0,
        })
        self.assertEqual(dest.employee_id, self.employee)
        self.assertEqual(dest.company_id, self.company_b)

    def test_device_user_list_no_profile_picture_column(self):
        xml = self.env.ref("tam_hr_zk_attendance.zk_device_user_view_list").arch_db
        self.assertNotIn('name="image_1920"', xml)
        form = self.env.ref("tam_hr_zk_attendance.zk_device_user_view_form").arch_db
        self.assertIn('name="image_1920"', form)
