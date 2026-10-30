# -*- coding: utf-8 -*-
"""v0.55 regression coverage. Run inside an Odoo 19 test database."""
import base64
import io

from PIL import Image
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestBatchSecurityPushTransfer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        registry = (
            "MultiBioDataSupport=0:1:0:0:0:0:0:0:0:1:0,"
            "MultiBioVersion=0:13.0:0:0:0:0:0:0:0:36.1:0,"
            "MaxPackageSize=2048000"
        )
        common = {"device_type": "acc", "is_approved": True,
                  "registry_payload": registry, "company_id": cls.env.company.id}
        cls.source = cls.env["zk.device"].create(dict(
            common, name="Batch v55 source", serial_number="BATCH-SOURCE-55",
        ))
        cls.target = cls.env["zk.device"].create(dict(
            common, name="Batch v55 target", serial_number="BATCH-TARGET-55",
            last_user_sync_at=cls.env["zk.device"]._online_cutoff(),
        ))
        cls.users = cls.env["zk.device.user"].create([
            {"device_id": cls.source.id, "pin": "8201", "name": "First User", "privilege": 0},
            {"device_id": cls.source.id, "pin": "8202", "name": "Second User", "privilege": 0},
        ])

    @staticmethod
    def _picture():
        out = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(out, format="JPEG")
        return base64.b64encode(out.getvalue())

    def _batch(self, mode="full"):
        return self.env["zk.device.user.batch.transfer.wizard"].create({
            "device_user_ids": [(6, 0, self.users.ids)],
            "source_device_id": self.source.id,
            "target_device_id": self.target.id,
            "transfer_mode": mode,
            "confirm_transfer": True,
        })

    def _commands(self):
        return self.env["zk.device.command"].sudo().search([
            ("device_id", "=", self.target.id),
        ], order="id asc")

    def test_batch_server_action_loads_on_odoo_19(self):
        """Regression: ir.actions.server has no groups_id field in Odoo 19."""
        action = self.env.ref(
            "tam_hr_zk_attendance.zk_device_user_batch_transfer_server_action"
        )
        self.assertEqual(action._name, "ir.actions.server")
        self.assertEqual(action.binding_model_id.model, "zk.device.user")
        self.assertEqual(action.binding_view_types, "list")
        self.assertEqual(
            action.code, "action = records.action_open_batch_transfer_wizard()"
        )
        self.assertNotIn("groups_id", action._fields)

    def test_action_opens_exact_selected_users(self):
        action = self.users.action_open_batch_transfer_wizard()
        wizard = self.env["zk.device.user.batch.transfer.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.device_user_ids, self.users)
        self.assertEqual(wizard.source_device_id, self.source)

    def test_batch_action_opens_for_classic_source(self):
        """Classic is a valid protocol family, not an ACC alias."""
        self.source.write({"device_type": "att"})
        action = self.users.action_open_batch_transfer_wizard()
        self.assertEqual(action["res_model"], "zk.device.user.batch.transfer.wizard")
        self.assertFalse(self._commands())

    def test_batch_action_reports_unapproved_source_without_queuing(self):
        self.source.write({"is_approved": False})
        with self.assertRaisesRegex(UserError, r"BATCH-SOURCE-55.*not approved"):
            self.users.action_open_batch_transfer_wizard()
        self.assertFalse(self._commands())

    def test_batch_submission_rechecks_source_protocol(self):
        wizard = self._batch()
        self.source.write({"device_type": "att"})
        with self.assertRaisesRegex(UserError, r"Cross-protocol biometric transfers"):
            wizard.action_transfer()
        self.assertFalse(self._commands())

    def test_batch_submission_rechecks_destination_approval(self):
        wizard = self._batch()
        self.target.write({"is_approved": False})
        with self.assertRaisesRegex(UserError, r"target device BATCH-TARGET-55.*not approved"):
            wizard.action_transfer()
        self.assertFalse(self._commands())

    def test_batch_full_transfer_commands_chained_across_users(self):
        self._batch().action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 6)
        self.assertEqual(commands[0].operation, "Complete transfer: create normal user profile")
        self.assertTrue(commands[3].command.startswith("DATA UPDATE user "))
        for current, previous in zip(commands[1:], commands[:-1]):
            self.assertEqual(current.depends_on_id, previous)

    def test_conflict_preflights_every_user_before_any_queue(self):
        self.env["zk.device.user"].create({
            "device_id": self.target.id, "pin": "8202",
            "name": "Wrong Person", "privilege": 0,
        })
        with self.assertRaises(UserError):
            self._batch().action_transfer()
        self.assertFalse(self._commands())

    def test_photo_only_bulk_repairs_existing_matching_users(self):
        photo = self._picture()
        self.users.write({"image_1920": photo})
        for user in self.users:
            self.env["zk.device.user"].create({
                "device_id": self.target.id, "pin": user.pin,
                "name": user.name, "privilege": 0,
            })
        self._batch("photo_only").action_transfer()
        commands = self._commands()
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(cmd.command.startswith("DATA UPDATE userpic ") for cmd in commands))
        self.assertEqual(commands[1].depends_on_id, commands[0])

    def test_photo_pull_queues_single_bulk_query(self):
        self.target.action_pull_profile_pictures()
        commands = self._commands()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands.command,
                         "DATA QUERY tablename=userpic,fielddesc=*,filter=*")
        with self.assertRaises(UserError):
            self.target.action_pull_profile_pictures()

    def test_classic_photo_sync_queues_check_then_log(self):
        self.target.device_type = "att"
        self.target.action_pull_profile_pictures()
        commands = self._commands()
        self.assertEqual(commands.mapped("command"), ["CHECK", "LOG"])
        self.assertEqual(commands[1].depends_on_id, commands[0])

