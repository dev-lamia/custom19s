# -*- coding: utf-8 -*-
"""Regression tests for malformed Classic ADMS name updates (v0.62)."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestClassicAdmsNameUpdate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env["zk.device"].sudo().create({
            "name": "Classic name-update test",
            "serial_number": "TEST-CLASSIC-NAME-62",
            "device_type": "att",
            "is_approved": True,
        })
        cls.User = cls.env["zk.device.user"].sudo()
        cls.Command = cls.env["zk.device.command"].sudo()
        cls.person = cls.User.create({
            "device_id": cls.device.id,
            "pin": "9012",
            "name": "zeeshan",
            "privilege": 14,
            "password": "passwd12",
            "card": "98765",
            "group_id": "1",
            "timezone": "0",
        })

    def _commands(self):
        return self.Command.search([("device_id", "=", self.device.id)])

    def test_classic_update_uses_tabs_and_preserves_existing_admin_privilege(self):
        self.person.action_update_device_name()
        commands = self._commands()
        self.assertEqual(len(commands), 1)
        command = commands.command
        self.assertEqual(
            command,
            "DATA USER PIN=9012\tName=zeeshan\tPri=14\tPasswd=passwd12\tCard=98765\tGrp=1\tTZ=0",
        )
        self.assertEqual(command.count("\t"), 6)
        self.assertEqual(command.count("\\t"), 0)
        self.assertEqual(self.person.privilege, 14)

    def test_malformed_pin_is_rejected_without_queuing(self):
        malformed = self.User.create({
            "device_id": self.device.id,
            "pin": r"9012\tName=wrong\tPri=0",
            "name": "wrong",
        })
        with self.assertRaises(UserError):
            (self.person | malformed).action_update_device_name()
        self.assertFalse(self._commands())

    def test_name_with_new_field_or_escape_is_rejected(self):
        for unsafe in ("Name\tPri=14", r"Name\tPri=14", "Name=override"):
            self.person.name = unsafe
            with self.assertRaises(UserError):
                self.person.action_update_device_name()
        self.assertFalse(self._commands())

    def test_credentials_with_separator_are_rejected(self):
        self.person.password = "unsafe\tPri=14"
        with self.assertRaises(UserError):
            self.person.action_update_device_name()
        self.assertFalse(self._commands())

    def test_device_must_be_approved(self):
        self.device.is_approved = False
        with self.assertRaises(UserError):
            self.person.action_update_device_name()
        self.assertFalse(self._commands())

    def test_pending_command_blocks_update(self):
        self.device.queue_adms_command("DATA QUERY USERINFO", "Read users")
        with self.assertRaises(UserError):
            self.person.action_update_device_name()
        self.assertEqual(len(self._commands()), 1)
