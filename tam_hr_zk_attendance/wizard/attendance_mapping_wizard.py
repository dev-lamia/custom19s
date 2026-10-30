# -*- coding: utf-8 -*-
import datetime
import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ZkAttendanceMappingWizard(models.TransientModel):
    _name = "zk.attendance.mapping.wizard"
    _description = "Map or Correct Historical Biometric Punches"

    device_user_id = fields.Many2one("zk.device.user", required=True, readonly=True, ondelete="cascade")
    device_id = fields.Many2one(related="device_user_id.device_id", string="Device", readonly=True)
    pin = fields.Char(related="device_user_id.pin", string="Device PIN", readonly=True)
    employee_id = fields.Many2one(related="device_user_id.employee_id", string="Current Employee", readonly=True)
    employee_public_id = fields.Many2one(
        related="device_user_id.employee_public_id", string="Current Employee (Public Directory)", readonly=True,
    )
    company_id = fields.Many2one(related="device_user_id.company_id", readonly=True)
    # Non-HR biometric managers can search hr.employee.public without obtaining
    # access to private HR records. The public view shares IDs with hr.employee;
    # target resolution below checks public visibility and company again on the server.
    correct_employee_public_id = fields.Many2one(
        "hr.employee.public",
        string="Correct Employee",
        help="Select an existing employee from a company you are authorized to access. Create missing employees in Employees first.",
    )
    eligible_employee_company_ids = fields.Many2many(
        "res.company", compute="_compute_eligible_employee_company_ids",
        compute_sudo=False, string="Permitted Employee Companies",
    )
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    workflow = fields.Selection([
        ("map", "Map past punches"),
        ("correct", "Fix wrong employee"),
    ], required=True, readonly=True, default=lambda self: self.env.context.get("default_workflow", "map"))
    mapping_mode = fields.Selection([
        ("map_only", "Link unmapped raw punches only"),
        ("map_rebuild", "Link punches and rebuild Odoo attendance"),
    ], required=True, default=lambda self: self.env.context.get("default_mapping_mode", "map_only"))
    correction_mode = fields.Selection([
        ("correct_raw", "Move raw punches only"),
        ("correct_attendance", "Move punches and rebuild Odoo attendance"),
    ], required=True, default=lambda self: self.env.context.get("default_correction_mode", "correct_raw"))
    # Retained for RPC/backward compatibility; the form exposes only the two choices for its workflow.
    mode = fields.Selection([
        ("map_only", "Map unmapped raw punches only"),
        ("map_rebuild", "Map unmapped punches and rebuild attendance"),
        ("correct_raw", "Correct raw mapping only"),
        ("correct_attendance", "Correct mapping and attendance"),
    ], required=True, default=lambda self: self.env.context.get("default_mode", "map_only"))
    confirm_rebuild = fields.Boolean(string="I understand this changes only derived attendance for the selected device PIN and dates")
    matching_log_count = fields.Integer(string="Raw Punches Found", compute="_compute_counts", readonly=True)
    current_employee_log_count = fields.Integer(string="Currently Mapped to Current Employee", compute="_compute_counts", readonly=True)

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_eligible_employee_company_ids(self):
        allowed = self.env.user.company_ids
        for wizard in self:
            wizard.eligible_employee_company_ids = allowed

    @api.onchange("mapping_mode")
    def _onchange_mapping_mode(self):
        if self.workflow == "map":
            self.mode = self.mapping_mode

    @api.onchange("correction_mode")
    def _onchange_correction_mode(self):
        if self.workflow == "correct":
            self.mode = self.correction_mode

    def _check_correction_access(self):
        """Allow privileged writes only for the selected, authorized device company.

        ``sudo`` is needed for private HR/raw attendance records, but must never
        be used before checking the manager's real multi-company permissions.
        """
        self.ensure_one()
        company = self.company_id
        if not company or company not in self.env.user.company_ids:
            raise UserError(_("You are not allowed to correct employees for this device company."))
        # Also enforce the device-user ACL and record rules on this exact mapping.
        self.device_user_id.with_company(company).check_access("write")
        return company

    def _correct_target_employee(self, company):
        """Resolve public employee choice while enforcing both-company rights.

        Do not grant HR-model access: the employee must be visible in
        hr.employee.public under the caller's authorized companies before
        private employee resolution under narrowly scoped sudo().
        """
        self.ensure_one()
        if not self.correct_employee_public_id:
            raise ValidationError(_("Choose the correct existing employee."))
        allowed_companies = self.env.user.company_ids.ids
        if company.id not in allowed_companies:
            raise UserError(_("You are not allowed to manage this device company."))
        public_employee = self.env["hr.employee.public"].with_context(
            allowed_company_ids=allowed_companies
        ).search([
            ("id", "=", self.correct_employee_public_id.id),
            ("company_id", "in", allowed_companies),
        ], limit=1)
        if not public_employee:
            raise ValidationError(_("The selected employee is not visible in your permitted companies."))

        # hr.employee.public shares private hr.employee IDs. Elevation is used
        # ONLY after checking public visibility and authorized company rights.
        employee = self.env["hr.employee"].sudo().browse(public_employee.id).exists()
        if not employee or employee.company_id.id not in allowed_companies:
            raise ValidationError(_("The selected employee must belong to one of your permitted companies."))
        if self.employee_id and employee.id == self.employee_id.id:
            raise ValidationError(_("Choose a different employee. This PIN is already mapped to that employee."))
        return employee

    def _timezone(self):
        self.ensure_one()
        try:
            return pytz.timezone(self.device_id.tz or "UTC")
        except Exception:
            return pytz.UTC

    def _utc_bounds(self):
        self.ensure_one()
        timezone = self._timezone()
        start = end = False
        if self.date_from:
            start = timezone.localize(datetime.datetime.combine(self.date_from, datetime.time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        if self.date_to:
            end = timezone.localize(datetime.datetime.combine(self.date_to, datetime.time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        return start, end

    def _domain(self, only_unmapped=False):
        self.ensure_one()
        domain = [("device_id", "=", self.device_id.id), ("device_id_num", "=", self.pin)]
        if only_unmapped:
            domain.append(("employee_id", "=", False))
        start, end = self._utc_bounds()
        if start:
            domain.append(("punching_time", ">=", fields.Datetime.to_string(start)))
        if end:
            domain.append(("punching_time", "<=", fields.Datetime.to_string(end)))
        return domain

    @api.depends("device_user_id", "date_from", "date_to")
    def _compute_counts(self):
        Log = self.env["zk.machine.attendance"].sudo()
        for wizard in self:
            if not wizard.device_user_id:
                wizard.matching_log_count = 0
                wizard.current_employee_log_count = 0
                continue
            domain = wizard._domain()
            wizard.matching_log_count = Log.search_count(domain)
            wizard.current_employee_log_count = Log.search_count(domain + [("employee_id", "=", wizard.employee_id.id)]) if wizard.employee_id else 0

    def _validate_dates(self, required=False):
        if required and (not self.date_from or not self.date_to):
            raise ValidationError(_("Choose both From Date and To Date."))
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(_("The From Date must not be later than the To Date."))

    def _rebuild_attendance(self, employee):
        """Explicit opt-in only; never triggered automatically by module upgrade.

        A selected device/PIN chooses impacted days, but recomputation uses
        ALL raw punches of the employee across every mapped device/PIN.
        """
        self.ensure_one()
        Log = self.env["zk.machine.attendance"].sudo()
        Attendance = self.env["hr.attendance"].sudo()
        logs = Log.search(
            self._domain() + [("employee_id", "=", employee.id)],
            order="punching_time asc",
        )
        dates = sorted({employee._zk_workday_date(log.punching_time) for log in logs})
        created = updated = 0
        for work_date in dates:
            outcome = Attendance._zk_sync_employee_day(
                employee.id, work_date, finalize_missing=True,
            )
            if outcome == "created":
                created += 1
            elif outcome == "updated":
                updated += 1
            elif outcome == "conflict":
                _logger.warning(
                    "ZK explicit rebuild preserved conflicting HR history; "
                    "employee_id=%s day=%s device_id=%s pin=%s",
                    employee.id, work_date, self.device_id.id, self.pin,
                )
        return created, updated

    def action_apply(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_("Map an employee to this device PIN before processing history."))
        rebuild = self.mapping_mode == "map_rebuild"
        self._validate_dates(required=rebuild)
        if rebuild and not self.confirm_rebuild:
            raise ValidationError(_("Confirm the attendance rebuild before continuing."))
        logs = self.env["zk.machine.attendance"].sudo().search(self._domain(only_unmapped=True))
        logs.write({"employee_id": self.employee_id.id})
        created = updated = 0
        if rebuild:
            created, updated = self._rebuild_attendance(self.employee_id)
        message = _("%(mapped)s previously unmapped raw punch(es) were linked to %(employee)s.", mapped=len(logs), employee=self.employee_id.name)
        if rebuild:
            message += " " + _("Created %(created)s and updated %(updated)s biometric attendance record(s).", created=created, updated=updated)
        return self._notification(_("Historical mapping complete"), message)

    def _correct(self, rebuild=False):
        self.ensure_one()
        company = self._check_correction_access()
        self._validate_dates(required=True)
        target_employee = self._correct_target_employee(company)
        if rebuild and not self.confirm_rebuild:
            raise ValidationError(_("Confirm the attendance correction before continuing."))
        if rebuild:
            raise UserError(_(
                "Automatic historical correction/rebuild is disabled because "
                "one HR attendance can contain punches from several devices "
                "and PINs. Correct historical HR records separately through "
                "the reviewed Odoo shell procedure. Use raw-only correction "
                "here if appropriate."
            ))
        old_employee = self.employee_id
        logs = self.env["zk.machine.attendance"].sudo().search(self._domain())
        if not logs:
            raise ValidationError(_(
                "No raw punches match this device, biometric ID and date range. "
                "Nothing was changed; review the selected dates and device first."
            ))
        logs.write({"employee_id": target_employee.id})
        self.device_user_id.write({"employee_id": target_employee.id})
        created = updated = 0
        if rebuild:
            created, updated = self._rebuild_attendance(target_employee)
        message = _("%(count)s raw punch(es) and this exact device/PIN mapping were assigned to %(employee)s.", count=len(logs), employee=target_employee.name)
        return self._notification(_("Employee mapping corrected"), message)

    def action_correct_raw(self):
        return self._correct(rebuild=False)

    def action_correct_attendance(self):
        return self._correct(rebuild=True)

    def _notification(self, title, message):
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": title, "message": message, "type": "success", "sticky": False, "next": {"type": "ir.actions.act_window_close"}}}
