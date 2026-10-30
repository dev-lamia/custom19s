# -*- coding: utf-8 -*-
"""Deprecated compatibility transient model. It has no UI entry point."""
from odoo import fields, models


class ZkDeviceUserSyncWizard(models.TransientModel):
    _name = "zk.device.user.sync.wizard"
    _description = "Deprecated Device User Sync Compatibility"

    employee_id = fields.Many2one("hr.employee", readonly=True)
    device_id = fields.Many2one("zk.device")
    pin = fields.Char(string="Device PIN")
    device_name = fields.Char(string="Name on Device")
