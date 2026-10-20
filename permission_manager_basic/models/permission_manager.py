import ast

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.osv import expression
from odoo.tools import sql
from odoo.tools.safe_eval import safe_eval


class PermissionManagerPolicy(models.Model):
    _name = "permission.manager.policy"
    _description = "Access Management Policy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    name = fields.Char(string="Policy Name", required=True, tracking=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    state = fields.Selection(
        selection=[("active", "Active"), ("inactive", "Inactive")],
        string="Status",
        default="active",
        tracking=True,
        index=True,
    )
    force_read_only = fields.Boolean(string="Force Read-Only", tracking=True)
    block_debug_mode = fields.Boolean(string="Block Debug Mode", tracking=True)
    block_login = fields.Boolean(string="Block Login", tracking=True)
    hide_export_available_fields = fields.Boolean(
        string="Hide Export Available Fields",
        tracking=True,
        help=(
            "Hide the left-side Available Fields panel and import-compatible "
            "option in the Export Data dialog for users assigned to this policy."
        ),
    )

    user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="permission_manager_policy_res_users_rel",
        column1="policy_id",
        column2="user_id",
        string="Users",
        tracking=True,
    )
    apply_by_user_groups = fields.Boolean(
        string="Apply by User Groups",
        tracking=True,
        help=(
            "Apply this policy to users who belong to any selected User Group. "
            "Directly selected Users continue to receive the policy as well."
        ),
    )
    group_ids = fields.Many2many(
        comodel_name="res.groups",
        relation="permission_manager_policy_res_groups_rel",
        column1="policy_id",
        column2="group_id",
        string="User Groups",
        tracking=True,
        help="Odoo access groups whose members should receive this policy.",
    )
    apply_all_companies = fields.Boolean(
        string="Apply regardless Company",
        default=True,
        tracking=True,
    )
    company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="permission_manager_policy_res_company_rel",
        column1="policy_id",
        column2="company_id",
        string="Companies",
    )

    hidden_menu_line_ids = fields.One2many(
        comodel_name="permission.manager.hidden.menu.line",
        inverse_name="policy_id",
        string="Hidden Navigation Items",
        copy=True,
    )
    model_permission_line_ids = fields.One2many(
        comodel_name="permission.manager.model.permission.line",
        inverse_name="policy_id",
        string="Model Permissions",
        copy=True,
    )
    search_panel_line_ids = fields.One2many(
        comodel_name="permission.manager.search.panel.line",
        inverse_name="policy_id",
        string="Search Panel",
        copy=True,
    )
    field_permission_line_ids = fields.One2many(
        comodel_name="permission.manager.field.permission.line",
        inverse_name="policy_id",
        string="Field Controls",
        copy=True,
    )
    field_state_rule_line_ids = fields.One2many(
        comodel_name="permission.manager.field.state.rule.line",
        inverse_name="policy_id",
        string="Field State Rules",
        copy=True,
    )
    record_domain_rule_line_ids = fields.One2many(
        comodel_name="permission.manager.record.domain.rule.line",
        inverse_name="policy_id",
        string="Record Domain Rules",
        copy=True,
    )
    hide_button_tab_line_ids = fields.One2many(
        comodel_name="permission.manager.hide.button.tab.line",
        inverse_name="policy_id",
        string="Hide Buttons/Tabs",
        copy=True,
    )
    chatter_visibility_line_ids = fields.One2many(
        comodel_name="permission.manager.chatter.visibility.line",
        inverse_name="policy_id",
        string="Chatter Visibility",
        copy=True,
    )

    hidden_menu_count = fields.Integer(
        string="Hidden Menus",
        compute="_compute_line_counts",
    )
    model_permission_count = fields.Integer(
        string="Model Permissions",
        compute="_compute_line_counts",
    )
    field_permission_count = fields.Integer(
        string="Field Controls",
        compute="_compute_line_counts",
    )
    field_state_rule_count = fields.Integer(
        string="Field State Rules",
        compute="_compute_line_counts",
    )
    hide_button_tab_count = fields.Integer(
        string="Hide Buttons/Tabs",
        compute="_compute_line_counts",
    )
    chatter_visibility_count = fields.Integer(
        string="Chatter Visibility",
        compute="_compute_line_counts",
    )
    search_panel_count = fields.Integer(
        string="Search Panel",
        compute="_compute_line_counts",
    )
    record_domain_rule_count = fields.Integer(
        string="Record Domain Rules",
        compute="_compute_line_counts",
    )
    global_control_count = fields.Integer(
        string="Global Controls",
        compute="_compute_line_counts",
    )

    @api.depends(
        "hidden_menu_line_ids",
        "model_permission_line_ids",
        "search_panel_line_ids",
        "field_permission_line_ids",
        "field_state_rule_line_ids",
        "record_domain_rule_line_ids",
        "hide_button_tab_line_ids",
        "chatter_visibility_line_ids",
        "apply_all_companies",
        "force_read_only",
        "block_debug_mode",
        "block_login",
        "hide_export_available_fields",
    )
    def _compute_line_counts(self):
        for policy in self:
            policy.hidden_menu_count = len(policy.hidden_menu_line_ids)
            policy.model_permission_count = len(policy.model_permission_line_ids)
            policy.search_panel_count = len(policy.search_panel_line_ids)
            policy.field_permission_count = len(policy.field_permission_line_ids)
            policy.field_state_rule_count = len(policy.field_state_rule_line_ids)
            policy.record_domain_rule_count = len(policy.record_domain_rule_line_ids)
            policy.hide_button_tab_count = len(policy.hide_button_tab_line_ids)
            policy.chatter_visibility_count = len(policy.chatter_visibility_line_ids)
            policy.global_control_count = sum(
                (
                    not policy.apply_all_companies,
                    policy.force_read_only,
                    policy.block_debug_mode,
                    policy.block_login,
                    policy.hide_export_available_fields,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_permission_manager_menu_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched_fields = {
            "active",
            "state",
            "force_read_only",
            "block_debug_mode",
            "hide_export_available_fields",
            "user_ids",
            "apply_by_user_groups",
            "group_ids",
            "apply_all_companies",
            "company_ids",
            "hidden_menu_line_ids",
            "model_permission_line_ids",
            "search_panel_line_ids",
            "field_permission_line_ids",
            "field_state_rule_line_ids",
            "record_domain_rule_line_ids",
            "hide_button_tab_line_ids",
            "chatter_visibility_line_ids",
        }
        if watched_fields.intersection(vals):
            self._clear_permission_manager_menu_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self._clear_permission_manager_menu_cache()
        return result

    def _clear_permission_manager_menu_cache(self):
        """Clear every server-side menu cache affected by policy changes.

        Odoo keeps the loaded app/menu structure cached per user/debug context.
        Clearing only one helper cache can make add/delete rules appear stale.
        """
        for model_name in ("ir.ui.menu", "ir.ui.view"):
            model = self.env[model_name]
            for method_name in ("clear_caches", "_clear_cache"):
                method = getattr(model, method_name, None)
                if method:
                    method()
        registry_clear = getattr(self.env.registry, "clear_cache", None)
        if registry_clear:
            registry_clear()
        return True

    @api.model
    def _group_assignment_schema_ready(self):
        """Return whether the group-assignment database schema is available.

        This makes upgrades from releases created before group assignment safe:
        the Python code can be loaded before the module upgrade has created the
        new policy column and many2many relation table. Until then, policies
        continue to match directly assigned users only.
        """
        return (
            sql.column_exists(
                self.env.cr, self._table, "apply_by_user_groups"
            )
            and sql.table_exists(
                self.env.cr, "permission_manager_policy_res_groups_rel"
            )
        )

    @api.model
    def _assignment_domain_for_user(self, user, field_prefix=None):
        """Return a domain matching direct-user or selected-group assignment."""
        user = user.sudo()

        def _field(name):
            return f"{field_prefix}.{name}" if field_prefix else name

        direct_user_domain = [(_field("user_ids"), "in", [user.id])]

        # During an upgrade from a version that did not yet have group-based
        # assignment, the registry may load this Python code before PostgreSQL
        # has the new policy column/relation table. Never build a domain that
        # references those missing objects; direct-user assignment remains safe.
        if not self._group_assignment_schema_ready():
            return direct_user_domain

        group_ids = user.all_group_ids.ids
        if not group_ids:
            return direct_user_domain

        group_domain = [
            (_field("apply_by_user_groups"), "=", True),
            (_field("group_ids"), "in", group_ids),
        ]
        return expression.OR([direct_user_domain, group_domain])

    @api.model
    def _company_domain(self, company_ids, field_prefix=None):
        """Return the company-scope domain for a policy or policy relation."""
        def _field(name):
            return f"{field_prefix}.{name}" if field_prefix else name

        return expression.OR(
            [
                [(_field("apply_all_companies"), "=", True)],
                [(_field("company_ids"), "in", list(company_ids or []))],
            ]
        )

    @api.model
    def _applicability_domain_for_user(
        self, user, company_ids, field_prefix=None
    ):
        """Return assignment + company scope domain for the given user."""
        return expression.AND(
            [
                self._assignment_domain_for_user(user, field_prefix=field_prefix),
                self._company_domain(company_ids, field_prefix=field_prefix),
            ]
        )

    @api.model
    def _is_login_blocked_for_user(self, user_id):
        """Return True when an active policy blocks login for the user."""
        user = self.env["res.users"].sudo().browse(user_id)
        if not user.exists():
            return False

        company_ids = user.company_ids.ids or user.company_id.ids
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("block_login", "=", True),
                ],
                self._applicability_domain_for_user(user, company_ids),
            ]
        )
        return bool(self.sudo().search_count(domain))

    @api.model
    def _is_debug_blocked_for_user(self, user_id):
        """Return True when an active policy blocks debug mode for the user."""
        user = self.env["res.users"].sudo().browse(user_id)
        if not user.exists():
            return False

        company_ids = user.company_ids.ids or user.company_id.ids
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("block_debug_mode", "=", True),
                ],
                self._applicability_domain_for_user(user, company_ids),
            ]
        )
        return bool(self.sudo().search_count(domain))

    @api.model
    def _is_force_read_only_for_current_user(self):
        """Return True when an active policy forces current user read-only."""
        user = self.env.user
        company = self.env.company
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("force_read_only", "=", True),
                ],
                self._applicability_domain_for_user(user, [company.id]),
            ]
        )
        return bool(self.sudo().search_count(domain))

    @api.model
    def is_current_user_debug_blocked(self):
        """RPC helper used by backend assets to leave debug mode safely."""
        return self.sudo()._is_debug_blocked_for_user(self.env.uid)

    @api.model
    def is_current_user_export_available_fields_hidden(self):
        """Return whether the current user's export field browser is hidden."""
        user = self.env.user
        company = self.env.company
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("hide_export_available_fields", "=", True),
                ],
                self._applicability_domain_for_user(user, [company.id]),
            ]
        )
        return bool(self.sudo().search_count(domain))

    def action_activate_policy(self):
        for policy in self:
            policy.write({"state": "active", "active": True})
        return True

    def action_deactivate_policy(self):
        for policy in self:
            policy.write({"state": "inactive", "active": False})
        return True

    def action_open_hidden_menus(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Hidden Navigation Items"),
            "res_model": "permission.manager.hidden.menu.line",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_model_permissions(self):
        self.ensure_one()
        list_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_model_permission_list"
        )
        form_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_model_permission_form"
        )
        search_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_model_permission_search"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Model Permissions"),
            "res_model": "permission.manager.model.permission.line",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "search_view_id": search_view.id,
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_search_panel(self):
        self.ensure_one()
        list_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_search_panel_list"
        )
        form_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_search_panel_form"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Search Panel"),
            "res_model": "permission.manager.search.panel.line",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_record_domain_rules(self):
        self.ensure_one()
        list_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_record_domain_rule_list"
        )
        form_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_record_domain_rule_form"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Record Domain Rules"),
            "res_model": "permission.manager.record.domain.rule.line",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_global_controls(self):
        self.ensure_one()
        form_view = self.env.ref(
            "permission_manager_basic.view_permission_manager_global_controls_form"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Global Controls"),
            "res_model": "permission.manager.policy",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(form_view.id, "form")],
            "target": "new",
        }

    def action_open_field_permissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Field Controls"),
            "res_model": "permission.manager.field.permission.line",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_field_state_rules(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Field State Rules"),
            "res_model": "permission.manager.field.state.rule.line",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_hide_buttons_tabs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Hide Buttons/Tabs"),
            "res_model": "permission.manager.hide.button.tab.line",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    def action_open_chatter_visibility(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Chatter Visibility"),
            "res_model": "permission.manager.chatter.visibility.line",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }


class PermissionManagerHiddenMenuLine(models.Model):
    _name = "permission.manager.hidden.menu.line"
    _description = "Hidden Navigation Item"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    menu_id = fields.Many2one(
        comodel_name="ir.ui.menu",
        string="Menu Entry",
        required=True,
        ondelete="cascade",
        index=True,
    )
    parent_id = fields.Many2one(
        related="menu_id.parent_id",
        string="Parent Menu",
        store=False,
        readonly=True,
    )
    complete_name = fields.Char(
        related="menu_id.complete_name",
        string="Label",
        store=False,
        readonly=True,
    )
    condition_expression = fields.Char(
        string="Condition Domain",
        default="[]",
        help=(
            "Optional domain evaluated on the current user. The menu is hidden "
            "only when the current user matches it, for example: "
            "[('company_id', '=', 1)]. Leave empty to always hide."
        ),
    )
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        (
            "policy_menu_unique",
            "unique(policy_id, menu_id)",
            "The same menu is already added to this policy.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_permission_manager_menu_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"policy_id", "menu_id", "condition_expression", "active"}.intersection(vals):
            self._clear_permission_manager_menu_cache()
        return result

    def unlink(self):
        # Clear after delete, otherwise menu cache can be rebuilt while the
        # deleted line is still present in the database.
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    def _clear_permission_manager_menu_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.constrains("condition_expression")
    def _check_condition_expression(self):
        for line in self:
            if not line.condition_expression:
                continue
            try:
                domain = ast.literal_eval(line.condition_expression)
            except (ValueError, SyntaxError) as error:
                raise UserError(_("Invalid menu condition domain: %s") % error) from error
            if not isinstance(domain, list):
                raise UserError(_("Menu condition must be a valid domain list."))

    def _condition_matches_current_user(self):
        self.ensure_one()
        if not self.condition_expression:
            return True
        try:
            domain = ast.literal_eval(self.condition_expression)
            return bool(self.env.user.sudo().filtered_domain(domain))
        except (ValueError, SyntaxError, TypeError):
            return False

    @api.model
    def _get_hidden_menu_ids_for_current_user(self):
        # During module install/upgrade, menu loading can be called before
        # this table exists. Return no hidden menus until registry is ready.
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_hidden_menu_line"],
        )
        if not self.env.cr.fetchone()[0]:
            return set()

        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        lines = self.sudo().with_context(active_test=False).search(domain)
        lines = lines.filtered(lambda line: line._condition_matches_current_user())
        menu_ids = lines.mapped("menu_id").ids
        if not menu_ids:
            return set()
        all_menus = self.env["ir.ui.menu"].sudo().search(
            [("id", "child_of", menu_ids)]
        )
        return set(all_menus.ids)


class PermissionManagerModelPermissionLine(models.Model):
    _name = "permission.manager.model.permission.line"
    _description = "Model Permission Line"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    report_ids = fields.Many2many(
        comodel_name="ir.actions.report",
        relation="permission_manager_line_report_rel",
        column1="line_id",
        column2="report_id",
        string="Reports",
        domain="[('model', '=', model)]",
    )
    action_ids = fields.Many2many(
        comodel_name="ir.actions.actions",
        relation="permission_manager_line_action_rel",
        column1="line_id",
        column2="action_id",
        string="Actions",
        domain="[('binding_model_id', '=', model_id)]",
    )
    hidden_view_ids = fields.Many2many(
        comodel_name="ir.ui.view",
        relation="permission_manager_line_view_rel",
        column1="line_id",
        column2="view_id",
        string="Hidden Views",
        domain="[('model', '=', model)]",
    )
    hide_list_view = fields.Boolean(
        string="Hide List View",
        help=(
            "Remove the List option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_form_view = fields.Boolean(
        string="Hide Form View",
        help=(
            "Remove the Form option from the model view switcher when an action "
            "exposes Form as a switchable view. It does not blank or rewrite "
            "the underlying form architecture."
        ),
    )
    hide_kanban_view = fields.Boolean(
        string="Hide Kanban View",
        help=(
            "Remove the Kanban option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_calendar_view = fields.Boolean(
        string="Hide Calendar View",
        help=(
            "Remove the Calendar option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_pivot_view = fields.Boolean(
        string="Hide Pivot View",
        help=(
            "Remove the Pivot option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_graph_view = fields.Boolean(
        string="Hide Graph View",
        help=(
            "Remove the Graph option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_activity_view = fields.Boolean(
        string="Hide Activity View",
        help=(
            "Remove the Activity option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_map_view = fields.Boolean(
        string="Hide Map View",
        help=(
            "Remove the Map option from the model view switcher for users "
            "matched by the policy."
        ),
    )
    hide_model = fields.Boolean(
        string="Hide Model",
        help="Hide this model from menus and block access for selected users.",
    )
    hide_action_menu = fields.Boolean(
        string="Hide Actions Menu",
        help="Hide the top control panel Actions menu for this model.",
    )
    hide_custom_filter = fields.Boolean(
        string="Hide Custom Filter",
        help=(
            "Hide the Custom Filter... entry from the search dropdown for "
            "this model for users matched by the policy."
        ),
    )
    condition_expression = fields.Char(
        string="Condition Domain",
        default="[]",
        help=(
            "Optional domain configured with the graphical domain builder. "
            "It is stored for conditional model permission evaluation. "
            "Leave empty or use [] to apply the rule without a condition."
        ),
    )

    block_read = fields.Boolean(string="Read")
    block_create = fields.Boolean(string="Create")
    block_edit = fields.Boolean(string="Edit")
    block_delete = fields.Boolean(string="Delete")
    block_archive = fields.Boolean(string="Archive")
    block_unarchive = fields.Boolean(string="Unarchive")
    block_duplicate = fields.Boolean(string="Duplicate")
    block_import_data = fields.Boolean(string="Import")
    block_export_data = fields.Boolean(string="Export")
    block_spreadsheet = fields.Boolean(
        string="Spreadsheet",
        help=(
            "Hide the Spreadsheet entry from the Odoo 19 cog/action menu for "
            "this model for users matched by the policy."
        ),
    )

    _sql_constraints = [
        (
            "policy_model_unique",
            "unique(policy_id, model_id)",
            "The same model is already added to this policy.",
        )
    ]

    @api.onchange("model_id")
    def _onchange_model_id(self):
        for line in self:
            line.report_ids = False
            line.action_ids = False
            line.hidden_view_ids = False

    @api.constrains("model_id")
    def _check_model_id(self):
        for line in self:
            if line.model_id.transient:
                raise UserError(_("Transient models cannot be used here."))

    @api.constrains("condition_expression")
    def _check_condition_expression(self):
        for line in self:
            if not line.condition_expression:
                continue
            try:
                domain = ast.literal_eval(line.condition_expression)
            except (ValueError, SyntaxError) as error:
                raise UserError(
                    _("Invalid model permission condition domain: %s") % error
                ) from error
            if not isinstance(domain, list):
                raise UserError(
                    _("Model permission condition must be a valid domain list.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_permission_manager_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {
            "policy_id",
            "model_id",
            "report_ids",
            "action_ids",
            "hidden_view_ids",
            "hide_list_view",
            "hide_form_view",
            "hide_kanban_view",
            "hide_calendar_view",
            "hide_pivot_view",
            "hide_graph_view",
            "hide_activity_view",
            "hide_map_view",
            "hide_model",
            "hide_action_menu",
            "hide_custom_filter",
            "condition_expression",
            "block_read",
            "block_create",
            "block_edit",
            "block_delete",
            "block_archive",
            "block_unarchive",
            "block_duplicate",
            "block_import_data",
            "block_export_data",
            "block_spreadsheet",
        }.intersection(vals):
            self._clear_permission_manager_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    def _clear_permission_manager_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.model
    def _table_exists(self):
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_model_permission_line"],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _current_user_domain(self, model_name):
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        return expression.AND(
            [
                [
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )

    @api.model
    def _get_rules_for_current_user(self, model_name):
        if not self._table_exists():
            return self.browse()
        return self.sudo().with_context(active_test=False).search(
            self._current_user_domain(model_name)
        )

    @api.model
    def _operation_field_map(self):
        return {
            "hide_action_menu": "hide_action_menu",
            "read": "block_read",
            "create": "block_create",
            "write": "block_edit",
            "unlink": "block_delete",
            "archive": "block_archive",
            "unarchive": "block_unarchive",
            "copy": "block_duplicate",
            "import": "block_import_data",
            "export": "block_export_data",
            "spreadsheet": "block_spreadsheet",
        }

    def _is_unconditional_rule(self):
        self.ensure_one()
        condition = (self.condition_expression or "").strip()
        return not condition or condition == "[]"

    def _condition_matches_any_record(self, model_name, active_ids):
        """Return whether at least one selected record matches the rule domain."""
        self.ensure_one()
        if self._is_unconditional_rule():
            return True

        try:
            condition_domain = ast.literal_eval(self.condition_expression)
        except (ValueError, SyntaxError):
            return False
        if not isinstance(condition_domain, list):
            return False

        active_ids = list(
            dict.fromkeys(
                record_id for record_id in (active_ids or []) if record_id
            )
        )
        if not active_ids:
            return False

        return bool(
            self.env[model_name].sudo().search_count(
                [("id", "in", active_ids)] + condition_domain
            )
        )

    def _blocked_operations_from_rules(self):
        operation_field_map = self._operation_field_map()
        return {
            operation
            for operation, field_name in operation_field_map.items()
            if any(self.mapped(field_name))
        }

    @api.model
    def _get_blocked_operations_for_current_user(
        self, model_name, active_ids=None
    ):
        """Return model operations blocked for the current user.

        Unconditional rules apply everywhere. Conditional rules are evaluated
        against the records being operated on. If a multi-record operation
        contains at least one matching record, the whole operation is blocked
        to prevent bypassing a restricted record through a mixed selection.
        """
        rules = self._get_rules_for_current_user(model_name)
        if not rules:
            return set()

        active_ids = list(
            dict.fromkeys(
                record_id for record_id in (active_ids or []) if record_id
            )
        )
        if active_ids:
            rules = rules.filtered(
                lambda rule: rule._condition_matches_any_record(
                    model_name, active_ids
                )
            )
        else:
            # There is no record to evaluate while loading a generic view or
            # creating/importing new records. In that case only model-wide
            # (unconditional) rules are safe to apply.
            rules = rules.filtered(lambda rule: rule._is_unconditional_rule())

        return rules._blocked_operations_from_rules()

    @api.model
    def _is_model_hidden_for_current_user(self, model_name):
        rules = self._get_rules_for_current_user(model_name)
        return bool(rules and any(rules.mapped("hide_model")))

    @api.model
    def _get_hidden_model_names_for_current_user(self):
        if not self._table_exists():
            return set()
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("hide_model", "=", True),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        rules = self.sudo().with_context(active_test=False).search(domain)
        return set(rules.mapped("model"))

    def _condition_matches_records(self, model_name, active_ids):
        """Return whether every selected record matches this rule's domain.

        A conditional report/action is hidden only when the whole selection is
        homogeneous for that condition. Therefore, a mixed selection does not
        trigger conditional hiding.
        """
        self.ensure_one()
        expression = (self.condition_expression or "").strip()
        if not expression or expression == "[]":
            return True

        try:
            condition_domain = ast.literal_eval(expression)
        except (ValueError, SyntaxError):
            return False
        if not isinstance(condition_domain, list):
            return False

        active_ids = list(
            dict.fromkeys(
                record_id for record_id in (active_ids or []) if record_id
            )
        )
        if not active_ids:
            return False

        matching_count = self.env[model_name].sudo().search_count(
            [("id", "in", active_ids)] + condition_domain,
        )
        return matching_count == len(active_ids)

    @api.model
    def get_hidden_view_types_for_current_user(self, model_name):
        """Return model-level view types hidden for the current user.

        View-type availability is decided before a record exists, so these
        switches intentionally do not evaluate ``condition_expression``.
        Record-conditional visibility remains available through Specific Views
        and Field Controls.
        """
        if not model_name or model_name not in self.env:
            return []
        rules = self._get_rules_for_current_user(model_name)
        hidden_types = set()
        if any(rules.mapped("hide_list_view")):
            hidden_types.add("list")
        if any(rules.mapped("hide_form_view")):
            hidden_types.add("form")
        if any(rules.mapped("hide_kanban_view")):
            hidden_types.add("kanban")
        if any(rules.mapped("hide_calendar_view")):
            hidden_types.add("calendar")
        if any(rules.mapped("hide_pivot_view")):
            hidden_types.add("pivot")
        if any(rules.mapped("hide_graph_view")):
            hidden_types.add("graph")
        if any(rules.mapped("hide_activity_view")):
            hidden_types.add("activity")
        if any(rules.mapped("hide_map_view")):
            hidden_types.add("map")
        return sorted(hidden_types)

    @api.model
    def get_hidden_bindings_for_records(self, model_name, active_ids=None):
        """Return conditional report/action IDs hidden for selected records.

        Odoo loads generic bindings without selected record IDs. The ActionMenus
        OWL patch calls this method whenever the selection changes so domains
        such as picking_type_code = incoming are evaluated against the actual
        selected transfers.
        """
        if model_name not in self.env:
            return {
                "reports": [],
                "actions": [],
                "views": [],
                "hide_action_menu": False,
                "hide_custom_filter": False,
                "block_export": False,
                "block_spreadsheet": False,
                "blocked_operations": [],
            }

        rules = self._get_rules_for_current_user(model_name)
        applicable_rules = rules.filtered(
            lambda rule: rule._condition_matches_records(model_name, active_ids)
        )

        # Model operations are stricter than report/action visibility. For a
        # mixed selection, hide an operation as soon as any selected record is
        # protected by its condition. This mirrors the backend enforcement.
        operation_rules = rules.filtered(
            lambda rule: rule._condition_matches_any_record(
                model_name, active_ids
            )
            if active_ids
            else rule._is_unconditional_rule()
        )
        blocked_operations = operation_rules._blocked_operations_from_rules()

        return {
            "reports": applicable_rules.mapped("report_ids").ids,
            "actions": applicable_rules.mapped("action_ids").ids,
            "views": applicable_rules.mapped("hidden_view_ids").ids,
            "hide_action_menu": any(applicable_rules.mapped("hide_action_menu")),
            "hide_custom_filter": any(
                rules.filtered(lambda rule: rule._is_unconditional_rule()).mapped(
                    "hide_custom_filter"
                )
            ),
            "block_export": "export" in blocked_operations,
            "block_spreadsheet": "spreadsheet" in blocked_operations,
            "blocked_operations": sorted(blocked_operations),
        }

    @api.model
    def is_spreadsheet_blocked_for_current_user(self, model_name):
        """Return whether Spreadsheet must be hidden for this model/user.

        Spreadsheet is a model-level cog-menu capability.  It must therefore
        be decided while the list view is loading, before any record is
        selected.  Keeping this check independent from selected-record domains
        also avoids a false negative when the cog menu opens with no active IDs.
        """
        if not model_name or model_name not in self.env:
            return False
        rules = self._get_rules_for_current_user(model_name)
        return bool(rules.filtered(lambda rule: rule.block_spreadsheet))

    @api.model
    def _get_hidden_bindings_for_current_user(self, model_name):
        context = self.env.context
        active_ids = context.get("active_ids") or []
        if not active_ids and context.get("active_id"):
            active_ids = [context["active_id"]]
        hidden = self.get_hidden_bindings_for_records(model_name, active_ids)
        return {
            "reports": set(hidden["reports"]),
            "actions": set(hidden["actions"]),
            "views": set(hidden["views"]),
            "hide_action_menu": hidden["hide_action_menu"],
            "hide_custom_filter": hidden.get("hide_custom_filter", False),
            "block_export": hidden.get("block_export", False),
            "block_spreadsheet": hidden.get("block_spreadsheet", False),
            "blocked_operations": set(hidden.get("blocked_operations", [])),
        }


class PermissionManagerSearchPanelLine(models.Model):
    _name = "permission.manager.search.panel.line"
    _description = "Search Panel Access Line"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[("transient", "=", False)],
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )

    hide_search_menu = fields.Boolean(
        string="Hide Search Dropdown",
        help=(
            "Hide the complete search dropdown toggle and its Filters, Group By "
            "and Favorites panel for this model."
        ),
    )
    hide_filters = fields.Boolean(
        string="Hide Filters",
        help="Hide the Filters column from the search dropdown for this model.",
    )
    hide_group_by = fields.Boolean(
        string="Hide Group By",
        help="Hide the Group By column from the search dropdown for this model.",
    )
    hide_favorites = fields.Boolean(
        string="Hide Favorites",
        help="Hide the Favorites column from the search dropdown for this model.",
    )
    hide_custom_filter = fields.Boolean(
        string="Hide Custom Filter",
        help=(
            "Hide every Custom Filter entry point for this model, including "
            "the Search Panel, typed-search autocomplete, and editable "
            "search facet/pencil dialog."
        ),
    )
    hide_custom_group_by = fields.Boolean(
        string="Hide Custom Group By",
        help="Hide the Custom Group option from the Group By column.",
    )
    hide_save_current_search = fields.Boolean(
        string="Hide Save Current Search",
        help=(
            "Hide Odoo's Save current search control from Favorites while "
            "keeping existing favorite filters available."
        ),
    )

    _sql_constraints = [
        (
            "policy_search_panel_model_unique",
            "unique(policy_id, model_id)",
            "The same model is already configured in Search Panel for this policy.",
        )
    ]

    @api.constrains("model_id")
    def _check_model_id(self):
        for line in self:
            if line.model_id.transient:
                raise UserError(_("Transient models cannot be used here."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("policy_id")._clear_permission_manager_menu_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {
            "policy_id",
            "model_id",
            "hide_search_menu",
            "hide_filters",
            "hide_group_by",
            "hide_favorites",
            "hide_custom_filter",
            "hide_custom_group_by",
            "hide_save_current_search",
        }.intersection(vals):
            self.mapped("policy_id")._clear_permission_manager_menu_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    @api.model
    def _default_search_panel_access(self):
        return {
            "hide_search_menu": False,
            "hide_filters": False,
            "hide_group_by": False,
            "hide_favorites": False,
            "hide_custom_filter": False,
            "hide_custom_group_by": False,
            "hide_save_current_search": False,
        }

    @api.model
    def _current_user_domain(self, model_name):
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        return expression.AND(
            [
                [
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )

    @api.model
    def get_search_panel_access(self, model_name):
        """Return model-wise search dropdown restrictions for the current user."""
        result = self._default_search_panel_access()
        if not model_name or model_name not in self.env:
            return result

        if not sql.table_exists(self.env.cr, self._table):
            return result

        rules = self.sudo().with_context(active_test=False).search(
            self._current_user_domain(model_name)
        )
        for field_name in result:
            result[field_name] = any(rules.mapped(field_name))

        # Backward compatibility with v41 where Hide Custom Filter lived in
        # Model Permissions. Existing policies continue to work after upgrade,
        # while all new Search UI configuration is managed from Search Panel.
        legacy_model_permission = self.env[
            "permission.manager.model.permission.line"
        ]
        if (
            not result["hide_custom_filter"]
            and legacy_model_permission._table_exists()
        ):
            legacy_rules = legacy_model_permission._get_rules_for_current_user(
                model_name
            ).filtered(lambda rule: rule._is_unconditional_rule())
            result["hide_custom_filter"] = any(
                legacy_rules.mapped("hide_custom_filter")
            )

        return result


class PermissionManagerFieldPermissionLine(models.Model):
    _name = "permission.manager.field.permission.line"
    _description = "Field Permission Rule"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('model_id', '=', model_id)]",
    )
    field_name = fields.Char(
        related="field_id.name",
        string="Technical Field",
        store=True,
        readonly=True,
        index=True,
    )
    field_description = fields.Char(
        related="field_id.field_description",
        string="Field Label",
        store=False,
        readonly=True,
    )
    field_type = fields.Selection(
        related="field_id.ttype",
        string="Field Type",
        readonly=True,
    )
    active = fields.Boolean(string="Active", default=True)
    enable_attribute_rule = fields.Boolean(
        string="Enable Attribute Rule",
        default=True,
        help=(
            "Enable Hide, Read Only, Required, conditional attribute behavior, "
            "and view targeting for this field."
        ),
    )
    enable_domain_rule = fields.Boolean(
        string="Enable Domain Rule",
        default=False,
        help=(
            "Enable relational field domain filtering for this model. "
            "Use the Domain Rule tab to configure the relational field and domain."
        ),
    )
    apply_form = fields.Boolean(string="Form", default=True)
    apply_list = fields.Boolean(string="List", default=True)
    apply_kanban = fields.Boolean(string="Kanban", default=False)
    apply_search = fields.Boolean(string="Search", default=False)

    hide_field = fields.Boolean(
        string="Hide Field",
        help=(
            "When Condition is empty/[], hide this field globally from Form, "
            "List, Kanban, Search/Filter, Group By, Pivot/Graph and Export. "
            "When a Condition is set, the hide rule is record-based and uses "
            "the selected Apply On views."
        ),
    )
    read_only = fields.Boolean(string="Read Only")
    required = fields.Boolean(string="Required")
    no_import = fields.Boolean(string="No Import")
    no_export = fields.Boolean(string="No Export")

    condition_expression = fields.Char(
        string="Condition",
        default="[]",
        help=(
            "Optional condition for Hide Field, Read Only, and Required. "
            "Leave [] to apply the selected controls all the time."
        ),
    )
    relational_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Relational Field",
        ondelete="set null",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['many2one', 'many2many'])]",
        help="Optional relational field whose selectable records should be filtered.",
    )
    selection_domain = fields.Char(
        string="Selection Domain",
        default="[]",
        help="Optional domain for the selected relational field.",
    )
    enable_selection_filter = fields.Boolean(
        string="Filter Field Values",
        default=False,
        help=(
            "For Selection fields, restrict options; for Many2one fields, "
            "restrict related records. Other models and fields are unaffected."
        ),
    )
    allowed_selection_value_ids = fields.Many2many(
        comodel_name="ir.model.fields.selection",
        relation="permission_manager_field_allowed_selection_rel",
        column1="rule_id",
        column2="selection_id",
        string="Allowed Selection Values",
        help="Choose the Selection field's options that these users may select.",
    )
    related_model = fields.Char(
        related="field_id.relation", string="Related Model", readonly=True,
    )
    allowed_related_record_line_ids = fields.One2many(
        comodel_name="permission.manager.allowed.related.record",
        inverse_name="rule_id",
        string="Allowed Related Records",
        copy=True,
        help="For a Many2one field, choose which related records may be selected.",
    )

    _sql_constraints = [
        (
            "policy_model_field_unique",
            "unique(policy_id, model_id, field_id)",
            "The same field is already added to this policy.",
        )
    ]

    @api.onchange("model_id")
    def _onchange_model_id(self):
        for line in self:
            if line.field_id and line.field_id.model_id != line.model_id:
                line.field_id = False
                line.enable_selection_filter = False
                line.allowed_selection_value_ids = [fields.Command.clear()]
                line.allowed_related_record_line_ids = [fields.Command.clear()]
            if (
                line.relational_field_id
                and line.relational_field_id.model_id != line.model_id
            ):
                line.relational_field_id = False

    @api.onchange("field_id")
    def _onchange_selection_field_id(self):
        for line in self:
            # Never reuse the previous field's option IDs for another field.
            line.allowed_selection_value_ids = [fields.Command.clear()]
            line.allowed_related_record_line_ids = [fields.Command.clear()]
            if line.field_id and line.field_id.ttype not in {"selection", "many2one"}:
                line.enable_selection_filter = False

    @api.onchange("enable_attribute_rule")
    def _onchange_enable_attribute_rule(self):
        for line in self:
            if not line.enable_attribute_rule:
                line.hide_field = False
                line.read_only = False
                line.required = False
                line.condition_expression = "[]"

    @api.onchange("enable_domain_rule")
    def _onchange_enable_domain_rule(self):
        for line in self:
            if not line.enable_domain_rule:
                line.relational_field_id = False
                line.selection_domain = "[]"

    @api.constrains(
        "field_id", "enable_selection_filter", "allowed_selection_value_ids",
        "allowed_related_record_line_ids",
    )
    def _check_selection_filter(self):
        for line in self:
            if not line.enable_selection_filter:
                continue
            field = line.field_id
            if not field or field.ttype not in {"selection", "many2one"}:
                raise UserError(
                    _("Value Filter requires a Selection or Many2one field.")
                )
            if field.ttype == "selection":
                if not line.allowed_selection_value_ids:
                    raise UserError(_("Choose at least one Allowed Selection Value."))
                if any(
                    option.field_id != field
                    for option in line.allowed_selection_value_ids
                ):
                    raise UserError(
                        _("Allowed Selection Values must belong to the selected field.")
                    )
            else:
                if not line.allowed_related_record_line_ids:
                    raise UserError(_("Choose at least one Allowed Related Record."))
                relation = field.relation
                if not relation or relation not in self.env.registry:
                    raise UserError(_("The selected Many2one field has no valid model."))
                for option in line.allowed_related_record_line_ids:
                    if option.relation_model != relation or not option.record_id:
                        raise UserError(
                            _("Each Allowed Related Record must belong to the selected field's related model.")
                        )
                    if not self.env[relation].sudo().browse(option.record_id).exists():
                        raise UserError(
                            _("An Allowed Related Record no longer exists.")
                        )

    @api.constrains("field_id", "relational_field_id")
    def _check_field_id(self):
        protected_fields = {
            "id",
            "display_name",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "__last_update",
        }
        for line in self:
            if line.field_id and line.field_id.name in protected_fields:
                raise UserError(_("System technical fields cannot be controlled."))
            if (
                line.relational_field_id
                and line.relational_field_id.model_id != line.model_id
            ):
                raise UserError(
                    _("Relational Field must belong to the selected model.")
                )

    @api.model
    def _prepare_rule_mode_values(self, vals):
        vals = dict(vals)
        attribute_fields = ("hide_field", "read_only", "required")
        condition = vals.get("condition_expression")
        if any(vals.get(name) for name in attribute_fields) or (
            condition not in (None, "", "[]", False)
        ):
            vals.setdefault("enable_attribute_rule", True)

        selection_domain = vals.get("selection_domain")
        if vals.get("relational_field_id") or (
            selection_domain not in (None, "", "[]", False)
        ):
            vals.setdefault("enable_domain_rule", True)

        if vals.get("enable_attribute_rule") is False:
            vals.update(
                {
                    "hide_field": False,
                    "read_only": False,
                    "required": False,
                    "condition_expression": "[]",
                }
            )
        if vals.get("enable_domain_rule") is False:
            vals.update(
                {
                    "relational_field_id": False,
                    "selection_domain": "[]",
                }
            )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_rule_mode_values(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._clear_permission_manager_view_cache()
        return records

    def write(self, vals):
        vals = self._prepare_rule_mode_values(vals)
        result = super().write(vals)
        watched_fields = {
            "policy_id",
            "model_id",
            "field_id",
            "active",
            "enable_attribute_rule",
            "enable_domain_rule",
            "apply_form",
            "apply_list",
            "apply_kanban",
            "apply_search",
            "hide_field",
            "read_only",
            "required",
            "no_import",
            "no_export",
            "condition_expression",
            "relational_field_id",
            "selection_domain",
            "enable_selection_filter",
            "allowed_selection_value_ids",
            "allowed_related_record_line_ids",
        }
        if watched_fields.intersection(vals):
            self._clear_permission_manager_view_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    def _clear_permission_manager_view_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.model
    def _table_exists(self):
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_field_permission_line"],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_rules_for_current_user(self, model_name):
        if not self._table_exists():
            return self.browse()
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        return self.sudo().with_context(active_test=False).search(domain)

    @api.model
    def _get_field_rules_for_current_user(self, model_name):
        rules = self._get_rules_for_current_user(model_name)
        result = {
            "hide": set(),
            "readonly": set(),
            "required": set(),
            "no_import": set(),
            "no_export": set(),
            "apply": {},
            "allowed_selection": {},
            "allowed_related": {},
        }
        for rule in rules:
            field_name = rule.field_name
            if not field_name:
                continue
            if rule.enable_selection_filter and rule.field_id.ttype == "selection":
                allowed = set(rule.allowed_selection_value_ids.mapped("value"))
                # If several applicable policies restrict the same field,
                # satisfy every policy rather than bypassing one of them.
                filters = result["allowed_selection"]
                if field_name in filters:
                    filters[field_name].intersection_update(allowed)
                else:
                    filters[field_name] = allowed
            if rule.enable_selection_filter and rule.field_id.ttype == "many2one":
                allowed = set(rule.allowed_related_record_line_ids.mapped("record_id"))
                filters = result["allowed_related"]
                if field_name in filters:
                    filters[field_name].intersection_update(allowed)
                else:
                    filters[field_name] = allowed
            apply_views = set()
            if rule.apply_form:
                apply_views.add("form")
            if rule.apply_list:
                apply_views.add("list")
                apply_views.add("tree")
            if rule.apply_kanban:
                apply_views.add("kanban")
            if rule.apply_search:
                apply_views.add("search")
            result["apply"].setdefault(field_name, set()).update(apply_views)

            condition = (rule.condition_expression or "").strip()
            is_conditional = condition not in {"", "[]", "False", "false", "0"}
            if not is_conditional:
                if rule.hide_field:
                    result["hide"].add(field_name)
                if rule.read_only:
                    result["readonly"].add(field_name)
                if rule.required:
                    result["required"].add(field_name)

            # Import/export restrictions are model metadata restrictions and do
            # not have a record context, so they always apply when selected.
            if rule.no_import:
                result["no_import"].add(field_name)
            if rule.no_export:
                result["no_export"].add(field_name)
        return result

    @api.model
    def _get_state_rules_for_current_user(self, model_name):
        result = []
        normalizer = self.env[
            "permission.manager.field.state.rule.line"
        ]._normalize_condition_expression
        for rule in self._get_rules_for_current_user(model_name):
            field_name = rule.field_name
            condition = (rule.condition_expression or "").strip()
            if (
                not field_name
                or condition in {"", "[]", "False", "false", "0"}
            ):
                continue

            apply_views = set()
            if rule.apply_form:
                apply_views.add("form")
            if rule.apply_list:
                apply_views.add("list")
                apply_views.add("tree")
            if rule.apply_kanban:
                apply_views.add("kanban")
            if not apply_views:
                continue

            expression = normalizer(condition)
            attribute_map = (
                ("invisible", rule.hide_field),
                ("readonly", rule.read_only),
                ("required", rule.required),
            )
            for attribute, enabled in attribute_map:
                if enabled:
                    result.append(
                        {
                            "field": field_name,
                            "attribute": attribute,
                            "expression": expression,
                            "apply": apply_views,
                        }
                    )
        return result



class PermissionManagerFieldStateRuleLine(models.Model):
    _name = "permission.manager.field.state.rule.line"
    _description = "Conditional Field State Rule"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    enable_attribute_rule = fields.Boolean(
        string="Enable Attribute Rule",
        default=False,
        help="Enable conditional invisible, readonly, or required behavior.",
    )
    enable_domain_rule = fields.Boolean(
        string="Enable Domain Rule",
        default=False,
        help="Keep this option for domain based field filtering rules.",
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Target Field",
        required=False,
        ondelete="cascade",
        index=True,
        domain="[('model_id', '=', model_id)]",
    )
    field_name = fields.Char(
        related="field_id.name",
        string="Technical Field",
        store=True,
        readonly=True,
        index=True,
    )
    field_description = fields.Char(
        related="field_id.field_description",
        string="Field Label",
        readonly=True,
    )
    attribute_behavior = fields.Selection(
        selection=[
            ("invisible", "Invisible"),
            ("readonly", "Readonly"),
            ("required", "Required"),
        ],
        string="Attribute Behavior",
        required=False,
        default=False,
        index=True,
    )
    condition_expression = fields.Char(
        string="Condition Expression",
        required=False,
        default="[]",
        help=(
            "Use a domain such as [('move_type', '=', 'out_invoice')] "
            "or a Python expression such as move_type == 'out_invoice'."
        ),
    )
    relational_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Relational Field",
        ondelete="set null",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['many2one', 'many2many'])]",
        help="Optional relational field used for domain based rules.",
    )
    selection_domain = fields.Char(
        string="Selection Domain",
        default="[]",
        help="Optional domain to apply on the relational/selection field.",
    )
    apply_form = fields.Boolean(string="Form", default=True)
    apply_list = fields.Boolean(string="List", default=False)
    apply_kanban = fields.Boolean(string="Kanban", default=False)
    active = fields.Boolean(string="Active", default=True)

    @api.onchange("model_id")
    def _onchange_model_id(self):
        for line in self:
            line.field_id = False
            line.relational_field_id = False

    @api.constrains("enable_attribute_rule", "field_id")
    def _check_attribute_rule_required_fields(self):
        for line in self:
            if line.enable_attribute_rule and not line.field_id:
                raise UserError(_("Target Field is required when Attribute Rule is enabled."))

    @api.constrains("field_id")
    def _check_field_id(self):
        protected_fields = {
            "id",
            "display_name",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "__last_update",
        }
        for line in self:
            if line.field_id.name in protected_fields:
                raise UserError(_("System technical fields cannot be controlled."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_permission_manager_view_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched_fields = {
            "policy_id",
            "model_id",
            "field_id",
            "attribute_behavior",
            "condition_expression",
            "apply_form",
            "apply_list",
            "apply_kanban",
            "active",
        }
        if watched_fields.intersection(vals):
            self._clear_permission_manager_view_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id and self.field_id.model_id != self.model_id:
            self.field_id = False

    def _clear_permission_manager_view_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.model
    def _table_exists(self):
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_field_state_rule_line"],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_rules_for_current_user(self, model_name):
        if not self._table_exists():
            return self.browse()
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        return self.sudo().with_context(active_test=False).search(domain)

    def _domain_leaf_to_expression(self, leaf):
        field_name, operator, value = leaf
        value_repr = repr(value)
        operator_map = {
            "=": "==",
            "!=": "!=",
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
            "in": "in",
            "not in": "not in",
            "ilike": "ilike",
            "not ilike": "not ilike",
        }
        if operator in {"ilike", "not ilike"}:
            expression = "%s and %s.lower() in str(%s).lower()" % (
                field_name,
                value_repr,
                field_name,
            )
            if operator == "not ilike":
                return "not (%s)" % expression
            return expression
        return "%s %s %s" % (field_name, operator_map.get(operator, operator), value_repr)

    def _domain_to_expression(self, domain):
        if not isinstance(domain, list):
            return "True"
        tokens = list(domain)

        def parse(index):
            token = tokens[index]
            if token == "|":
                left, next_index = parse(index + 1)
                right, next_index = parse(next_index)
                return "(%s or %s)" % (left, right), next_index
            if token == "&":
                left, next_index = parse(index + 1)
                right, next_index = parse(next_index)
                return "(%s and %s)" % (left, right), next_index
            if token == "!":
                value, next_index = parse(index + 1)
                return "not (%s)" % value, next_index
            if isinstance(token, (tuple, list)) and len(token) == 3:
                return self._domain_leaf_to_expression(token), index + 1
            return "True", index + 1

        parts = []
        index = 0
        while index < len(tokens):
            part, index = parse(index)
            parts.append(part)
        return " and ".join("(%s)" % part for part in parts) if parts else "True"

    def _normalize_condition_expression(self, expression):
        expression = (expression or "").strip()
        if not expression:
            return "True"
        if expression.startswith("["):
            try:
                domain = ast.literal_eval(expression)
            except (SyntaxError, ValueError):
                return expression
            return self._domain_to_expression(domain)
        return expression

    @api.model
    def _get_state_rules_for_current_user(self, model_name):
        result = []
        for rule in self._get_rules_for_current_user(model_name):
            apply_views = set()
            if rule.apply_form:
                apply_views.add("form")
            if rule.apply_list:
                apply_views.add("list")
                apply_views.add("tree")
            if rule.apply_kanban:
                apply_views.add("kanban")
            if not rule.field_name or not rule.attribute_behavior or not apply_views:
                continue
            result.append(
                {
                    "field": rule.field_name,
                    "attribute": rule.attribute_behavior,
                    "expression": rule._normalize_condition_expression(
                        rule.condition_expression
                    ),
                    "apply": apply_views,
                }
            )
        return result




class PermissionManagerRecordDomainRuleLine(models.Model):
    _name = "permission.manager.record.domain.rule.line"
    _description = "Record Domain Rule Line"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        readonly=True,
    )
    filter_expression = fields.Char(
        string="Filter Expression",
        default="[]",
        required=True,
        help=(
            "Static domain applied to records for the selected scopes. "
            "For a dynamic current-user condition, use Current User Field instead "
            "of typing uid/user.id in the graphical domain editor."
        ),
    )
    current_user_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Current User Field",
        domain=(
            "[('model_id', '=', model_id), ('ttype', '=', 'many2one'), "
            "('relation', '=', 'res.users')]"
        ),
        help=(
            "Optional user field used for a dynamic current-user filter. "
            "For example, choose Salesperson on Sales Order. The rule will "
            "automatically add (selected_field, '=', current logged-in user)."
        ),
    )
    soft_restriction = fields.Boolean(
        string="Soft Restriction",
        compute="_compute_soft_restriction",
        store=True,
        help=(
            "Automatically enabled when the rule is read-only. This keeps "
            "Scope Read as a simple list/search filter without requiring a "
            "second checkbox."
        ),
    )
    scope_read = fields.Boolean(string="Scope Read", default=True)
    scope_write = fields.Boolean(string="Scope Write")
    scope_create = fields.Boolean(string="Scope Create")
    scope_delete = fields.Boolean(string="Scope Delete")
    active = fields.Boolean(string="Active", default=True)

    @api.depends("scope_read", "scope_write", "scope_create", "scope_delete")
    def _compute_soft_restriction(self):
        for line in self:
            line.soft_restriction = bool(
                line.scope_read
                and not line.scope_write
                and not line.scope_create
                and not line.scope_delete
            )

    @api.constrains("filter_expression", "model_id")
    def _check_filter_expression(self):
        for line in self:
            if not line.filter_expression or not line.model_id:
                continue
            try:
                domain = line._evaluate_filter_domain()
                self.env[line.model].sudo().search_count(domain, limit=1)
            except Exception as error:
                raise UserError(
                    _("Invalid record domain for %(model)s: %(error)s")
                    % {
                        "model": line.model_id.display_name,
                        "error": error,
                    }
                ) from error

    def _evaluate_filter_domain(self, user=None):
        self.ensure_one()
        expression_text = self.filter_expression or "[]"
        eval_user = user or self.env.user
        eval_context = {
            "user": eval_user,
            "uid": eval_user.id,
            "current_logged_in_user": eval_user.id,
            "company": self.env.company,
            "company_ids": self.env.companies.ids,
            "context": dict(self.env.context),
        }
        domain = safe_eval(expression_text, eval_context)
        if not isinstance(domain, (list, tuple)):
            raise UserError(_("Filter Expression must evaluate to a domain list."))
        domain = list(domain)
        if self.current_user_field_id:
            domain = expression.AND(
                [
                    domain,
                    [(self.current_user_field_id.name, "=", eval_user.id)],
                ]
            )
        return domain

    @api.model
    def _get_applicable_rules(self, model_name, scope, include_soft=True):
        scope_field = {
            "read": "scope_read",
            "write": "scope_write",
            "create": "scope_create",
            "delete": "scope_delete",
        }.get(scope)
        if not scope_field:
            return self.browse()

        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("model", "=", model_name),
                    (scope_field, "=", True),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        if not include_soft:
            domain.append(("soft_restriction", "=", False))
        return self.sudo().search(domain)

    @api.model
    def _get_domain_for_current_user(self, model_name, scope, include_soft=True):
        rules = self._get_applicable_rules(
            model_name,
            scope,
            include_soft=include_soft,
        )
        domains = []
        for rule in rules:
            domains.append(rule._evaluate_filter_domain(user=self.env.user))
        return expression.AND(domains) if domains else []


class PermissionManagerHideItem(models.Model):
    _name = "permission.manager.hide.item"
    _description = "Hide Button/Tab Item"
    _order = "model_id, item_type, name"

    name = fields.Char(string="Label", required=True, index=True)
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    item_type = fields.Selection(
        selection=[("button", "Button"), ("tab", "Tab")],
        string="Type",
        required=True,
        index=True,
    )
    technical_key = fields.Char(string="Technical Key", required=True, index=True)
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        (
            "model_type_key_unique",
            "unique(model_id, item_type, technical_key)",
            "The same button or tab is already available for this model.",
        )
    ]


class PermissionManagerHideButtonTabLine(models.Model):
    _name = "permission.manager.hide.button.tab.line"
    _description = "Hide Buttons/Tabs Rule"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    hide_button_item_ids = fields.Many2many(
        comodel_name="permission.manager.hide.item",
        relation="permission_manager_line_button_item_rel",
        column1="line_id",
        column2="item_id",
        string="Hide Buttons",
        domain="[('model_id', '=', model_id), ('item_type', '=', 'button')]",
    )
    hide_tab_item_ids = fields.Many2many(
        comodel_name="permission.manager.hide.item",
        relation="permission_manager_line_tab_item_rel",
        column1="line_id",
        column2="item_id",
        string="Hide Tabs",
        domain="[('model_id', '=', model_id), ('item_type', '=', 'tab')]",
    )
    condition_expression = fields.Char(
        string="Condition",
        help=(
            "Optional domain on the selected model. Selected buttons/tabs are "
            "hidden only when this condition is true. Leave empty to always hide."
        ),
    )
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        (
            "policy_hide_model_unique",
            "unique(policy_id, model_id)",
            "The same model is already added for hide buttons/tabs.",
        )
    ]

    @api.constrains("condition_expression")
    def _check_condition_expression(self):
        for line in self:
            if not line.condition_expression:
                continue
            try:
                domain = ast.literal_eval(line.condition_expression)
            except (ValueError, SyntaxError) as error:
                raise UserError(_("Invalid button/tab condition domain: %s") % error) from error
            if not isinstance(domain, list):
                raise UserError(_("Button/tab condition must be a valid domain list."))

    def _normalized_condition_expression(self):
        self.ensure_one()
        if not self.condition_expression:
            return "True"
        return self.env[
            "permission.manager.field.state.rule.line"
        ]._normalize_condition_expression(self.condition_expression)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("model_id")._sync_permission_manager_hide_items()
        records._clear_permission_manager_view_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "model_id" in vals:
            self.mapped("model_id")._sync_permission_manager_hide_items()
        if {
            "policy_id",
            "model_id",
            "hide_button_item_ids",
            "hide_tab_item_ids",
            "condition_expression",
            "active",
        }.intersection(vals):
            self._clear_permission_manager_view_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id:
            self.model_id._sync_permission_manager_hide_items()

    def action_refresh_available_items(self):
        self.mapped("model_id")._sync_permission_manager_hide_items()
        return True

    def _clear_permission_manager_view_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.model
    def _get_hidden_item_keys_for_current_user(self, model_name):
        # During module install/upgrade, this override can be called before
        # the new SQL table is created. Return nothing until registry is ready.
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_hide_button_tab_line"],
        )
        if not self.env.cr.fetchone()[0]:
            return {"button": set(), "tab": set()}

        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        lines = self.sudo().with_context(active_test=False).search(domain)
        result = {"button": {}, "tab": {}}
        for line in lines:
            condition_expr = line._normalized_condition_expression()
            for item in line.hide_button_item_ids:
                result["button"][item.technical_key] = condition_expr
            for item in line.hide_tab_item_ids:
                result["tab"][item.technical_key] = condition_expr
        return result


class IrModel(models.Model):
    _inherit = "ir.model"

    def _sync_permission_manager_hide_items(self):
        for model_rec in self:
            self.env["permission.manager.hide.item"]._sync_from_model(model_rec)
        return True


class PermissionManagerHideItemSync(models.Model):
    _inherit = "permission.manager.hide.item"

    @api.model
    def _make_button_key(self, node):
        button_type = node.get("type") or ""
        button_name = node.get("name") or ""
        button_string = node.get("string") or ""
        return "button:%s:%s:%s" % (button_type, button_name, button_string)

    @api.model
    def _make_tab_key(self, node):
        tab_name = node.get("name") or ""
        tab_string = node.get("string") or ""
        return "tab:%s:%s" % (tab_name, tab_string)

    @api.model
    def _sync_from_model(self, model_rec):
        View = self.env["ir.ui.view"].sudo()
        views = View.search([("model", "=", model_rec.model), ("type", "=", "form")])
        values_by_key = {}
        for view in views:
            arch = view.arch_db
            if not arch:
                continue
            try:
                root = etree.fromstring(arch.encode("utf-8"))
            except etree.XMLSyntaxError:
                continue
            for button in root.xpath(".//button"):
                key = self._make_button_key(button)
                if key == "button:::":
                    continue

                # Buttons placed inside embedded x2many lists often use only
                # ``title`` and ``icon`` (no ``string``). Use title first so
                # entries such as the standard/custom "Duplicate Line" action
                # are easy to identify in Access Management without taking a
                # dependency on the module that adds the button.
                label = (
                    button.get("string")
                    or button.get("title")
                    or button.get("name")
                    or _("Unnamed Button")
                )
                button_name = button.get("name") or ""
                display_name = label
                if button_name and button_name != label:
                    display_name = _("%s — %s") % (label, button_name)

                values_by_key[("button", key)] = {
                    "name": display_name,
                    "model_id": model_rec.id,
                    "item_type": "button",
                    "technical_key": key,
                }
            for page in root.xpath(".//page"):
                key = self._make_tab_key(page)
                if key == "tab::":
                    continue
                label = page.get("string") or page.get("name") or _("Unnamed Tab")
                values_by_key[("tab", key)] = {
                    "name": _("Form Tab — %s") % label,
                    "model_id": model_rec.id,
                    "item_type": "tab",
                    "technical_key": key,
                }
        for (item_type, key), values in values_by_key.items():
            item = self.search(
                [
                    ("model_id", "=", model_rec.id),
                    ("item_type", "=", item_type),
                    ("technical_key", "=", key),
                ],
                limit=1,
            )
            if item:
                item.write({"name": values["name"], "active": True})
            else:
                self.create(values)
        return True


class PermissionManagerChatterVisibilityLine(models.Model):
    _name = "permission.manager.chatter.visibility.line"
    _description = "Chatter Visibility Rule"
    _order = "id desc"

    policy_id = fields.Many2one(
        comodel_name="permission.manager.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(
        related="model_id.model",
        string="Technical Model",
        store=True,
        readonly=True,
        index=True,
    )
    hide_chatter = fields.Boolean(string="Hide Chatter")
    hide_composer = fields.Boolean(string="Hide Composer")
    hide_log_note = fields.Boolean(string="Hide Log Note")
    hide_schedule_activity = fields.Boolean(string="Hide Schedule Activity")
    hide_search_messages = fields.Boolean(string="Hide Search Messages")
    hide_attachments = fields.Boolean(string="Hide Attachments")
    hide_followers = fields.Boolean(string="Hide Followers")
    hide_follow_button = fields.Boolean(string="Hide Follow Button")
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        (
            "policy_chatter_model_unique",
            "unique(policy_id, model_id)",
            "The same model is already added for chatter visibility.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_permission_manager_view_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched_fields = {
            "policy_id",
            "model_id",
            "hide_chatter",
            "hide_composer",
            "hide_log_note",
            "hide_schedule_activity",
            "hide_search_messages",
            "hide_attachments",
            "hide_followers",
            "hide_follow_button",
            "active",
        }
        if watched_fields.intersection(vals):
            self._clear_permission_manager_view_cache()
        return result

    def unlink(self):
        policies = self.mapped("policy_id")
        result = super().unlink()
        policies._clear_permission_manager_menu_cache()
        return result

    def _clear_permission_manager_view_cache(self):
        return self.env["permission.manager.policy"]._clear_permission_manager_menu_cache()

    @api.model
    def _table_exists(self):
        self.env.cr.execute(
            "SELECT to_regclass(%s)",
            ["permission_manager_chatter_visibility_line"],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_rules_for_current_user(self, model_name):
        if not self._table_exists():
            return self.browse()
        user = self.env.user
        company = self.env.company
        policy_domain = self.env[
            "permission.manager.policy"
        ]._applicability_domain_for_user(
            user, [company.id], field_prefix="policy_id"
        )
        domain = expression.AND(
            [
                [
                    ("active", "=", True),
                    ("model", "=", model_name),
                    ("policy_id.active", "=", True),
                    ("policy_id.state", "=", "active"),
                ],
                policy_domain,
            ]
        )
        return self.sudo().with_context(active_test=False).search(domain)

    @api.model
    def _get_flags_for_current_user(self, model_name):
        rules = self._get_rules_for_current_user(model_name)
        if not rules:
            return {}
        field_names = (
            "hide_chatter",
            "hide_composer",
            "hide_log_note",
            "hide_schedule_activity",
            "hide_search_messages",
            "hide_attachments",
            "hide_followers",
            "hide_follow_button",
        )
        return {field_name: any(rules.mapped(field_name)) for field_name in field_names}


class Base(models.AbstractModel):
    _inherit = "base"

    def _permission_manager_is_internal_model(self):
        """Keep framework/bootstrap models outside dynamic record controls.

        ``res.partner`` is intentionally *not* protected. Contacts are a normal
        business model and must respect permissions configured from the Access
        Management UI. Only the small set of ``res.*`` models required for
        session/company/language bootstrap stay protected.
        """
        protected_prefixes = (
            "permission.manager.",
            "ir.",
            "mail.",
            "web.",
            "bus.",
            "base.",
        )
        protected_models = {
            "res.users",
            "res.groups",
            "res.company",
            "res.config.settings",
            "res.lang",
            "res.currency",
            "res.country",
            "res.country.state",
        }
        return (
            self._name in protected_models
            or self._name.startswith(protected_prefixes)
        )

    def _permission_manager_blocked_operations(self):
        if self._permission_manager_is_internal_model():
            return set()
        model_permission = self.env["permission.manager.model.permission.line"]
        blocked_ops = set(
            model_permission._get_blocked_operations_for_current_user(
                self._name, self.ids
            )
        )
        if model_permission._is_model_hidden_for_current_user(self._name):
            blocked_ops.update(
                {
                    "read",
                    "create",
                    "write",
                    "unlink",
                    "archive",
                    "unarchive",
                    "copy",
                    "import",
                    "export",
                }
            )
        if self.env["permission.manager.policy"]._is_force_read_only_for_current_user():
            blocked_ops.update(
                {
                    "create",
                    "write",
                    "unlink",
                    "archive",
                    "unarchive",
                    "copy",
                    "import",
                    "export",
                }
            )
        return blocked_ops

    def _permission_manager_field_rules(self):
        if self._permission_manager_is_internal_model():
            return {
                "hide": set(),
                "readonly": set(),
                "required": set(),
                "no_import": set(),
                "no_export": set(),
                "apply": {},
                "allowed_selection": {},
                "allowed_related": {},
            }
        return self.env[
            "permission.manager.field.permission.line"
        ]._get_field_rules_for_current_user(self._name)

    def _permission_manager_field_state_rules(self):
        if self._permission_manager_is_internal_model():
            return []
        unified_rules = self.env[
            "permission.manager.field.permission.line"
        ]._get_state_rules_for_current_user(self._name)
        legacy_rules = self.env[
            "permission.manager.field.state.rule.line"
        ]._get_state_rules_for_current_user(self._name)
        return unified_rules + legacy_rules

    def _permission_manager_record_domain(self, scope, include_soft=True):
        if (
            self.env.context.get("permission_manager_skip_record_domain")
            or self._permission_manager_is_internal_model()
        ):
            return []
        return self.env[
            "permission.manager.record.domain.rule.line"
        ]._get_domain_for_current_user(
            self._name,
            scope,
            include_soft=include_soft,
        )

    @api.model
    def web_search_read(self, domain, *args, **kwargs):
        """Filter only web list/search results for configured Scope Read rules.

        This intentionally does not alter ``read()``, ``_search()``, session, menu,
        action, or other framework operations.  That keeps Odoo web bootstrap safe
        while still hiding non-matching rows in list/search views.
        """
        if (
            self.env.context.get("permission_manager_skip_record_domain")
            or self._permission_manager_is_internal_model()
        ):
            return super().web_search_read(domain, *args, **kwargs)

        record_domain = self._permission_manager_record_domain(
            "read",
            include_soft=True,
        )
        if record_domain:
            domain = expression.AND([domain or [], record_domain])

        safe_self = self.with_context(permission_manager_skip_record_domain=True)
        return super(Base, safe_self).web_search_read(domain, *args, **kwargs)

    def _permission_manager_check_field_values(self, vals, create_mode=False):
        if self.env.context.get("permission_manager_skip_check"):
            return True
        if self._permission_manager_is_internal_model() or not vals:
            return True

        field_rules = self._permission_manager_field_rules()
        readonly_fields = field_rules.get("readonly", set()) | field_rules.get(
            "hide", set()
        )
        blocked_changed_fields = sorted(readonly_fields.intersection(vals))
        if blocked_changed_fields:
            labels = []
            for field_name in blocked_changed_fields:
                field = self._fields.get(field_name)
                labels.append(field.string if field else field_name)
            raise UserError(
                _("Access Management keeps these fields read-only: %s")
                % ", ".join(labels)
            )

        for field_name, allowed in field_rules.get("allowed_selection", {}).items():
            if field_name not in vals:
                continue
            value = vals[field_name]
            # Clearing an optional field remains allowed; existing records
            # are not rewritten merely because their old option is hidden.
            if value is False or value is None or value == "":
                continue
            if str(value) not in allowed:
                field = self._fields.get(field_name)
                raise UserError(
                    _("Access Management does not allow value %(value)s for %(field)s.")
                    % {
                        "value": str(value),
                        "field": field.string if field else field_name,
                    }
                )

        for field_name, allowed in field_rules.get("allowed_related", {}).items():
            if field_name not in vals or vals[field_name] in (False, None, ""):
                continue
            value = vals[field_name]
            if not isinstance(value, int) or isinstance(value, bool) or value not in allowed:
                field = self._fields.get(field_name)
                raise UserError(
                    _("Access Management does not allow this value for %s.")
                    % (field.string if field else field_name)
                )

        required_fields = field_rules.get("required", set())
        if create_mode:
            missing_fields = []
            for field_name in sorted(required_fields):
                field = self._fields.get(field_name)
                if not field or field_name not in vals or vals.get(field_name) in (
                    False,
                    None,
                    "",
                    [],
                ):
                    missing_fields.append(field.string if field else field_name)
            if missing_fields:
                raise UserError(
                    _("Access Management requires these fields: %s")
                    % ", ".join(missing_fields)
                )
        else:
            empty_required_fields = []
            for field_name in sorted(required_fields.intersection(vals)):
                if vals.get(field_name) in (False, None, "", []):
                    field = self._fields.get(field_name)
                    empty_required_fields.append(field.string if field else field_name)
            if empty_required_fields:
                raise UserError(
                    _("Access Management requires these fields: %s")
                    % ", ".join(empty_required_fields)
                )
        return True

    def _permission_manager_check_operation(self, operation):
        if self.env.context.get("permission_manager_skip_check"):
            return True
        if operation in self._permission_manager_blocked_operations():
            labels = {
                "read": _("read"),
                "create": _("create"),
                "write": _("edit"),
                "unlink": _("delete"),
                "archive": _("archive"),
                "unarchive": _("unarchive"),
                "copy": _("duplicate"),
                "import": _("import"),
                "export": _("export"),
            }
            message = _("Access Management blocks %(operation)s on %(model)s.") % {
                "operation": labels.get(operation, operation),
                "model": self._description or self._name,
            }
            if operation == "read":
                raise AccessError(message)
            raise UserError(message)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        self._permission_manager_check_operation("create")
        for vals in vals_list:
            self._permission_manager_check_field_values(vals, create_mode=True)
        return super().create(vals_list)

    def write(self, vals):
        if "active" in vals and len(vals) == 1:
            self._permission_manager_check_operation(
                "unarchive" if vals.get("active") else "archive"
            )
        else:
            self._permission_manager_check_operation("write")
        self._permission_manager_check_field_values(vals, create_mode=False)
        return super().write(vals)

    def unlink(self):
        self._permission_manager_check_operation("unlink")
        return super().unlink()

    def copy(self, default=None):
        self._permission_manager_check_operation("copy")
        return super().copy(default=default)

    def read(self, fields=None, load="_classic_read"):
        self._permission_manager_check_operation("read")
        return super().read(fields=fields, load=load)

    def export_data(self, fields_to_export):
        """Enforce model and field-level Export restrictions server-side."""
        self._permission_manager_check_operation("export")
        field_rules = self._permission_manager_field_rules()
        restricted_fields = field_rules.get("no_export", set()) | field_rules.get(
            "hide", set()
        )
        blocked_fields = {
            field_path.split("/", 1)[0]
            for field_path in fields_to_export or []
            if field_path and field_path.split("/", 1)[0] in restricted_fields
        }
        if blocked_fields:
            labels = []
            for field_name in sorted(blocked_fields):
                field = self._fields.get(field_name)
                labels.append(field.string if field else field_name)
            raise UserError(
                _("Access Management blocks exporting these fields: %s")
                % ", ".join(labels)
            )
        return super().export_data(fields_to_export)

    @api.model
    def load(self, fields, data):
        """Enforce the Import checkbox on the server-side import endpoint."""
        self._permission_manager_check_operation("import")
        return super().load(fields, data)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        if self.env.context.get("permission_manager_skip_view_hide"):
            return result

        field_rules = self._permission_manager_field_rules()
        hidden_fields = field_rules.get("hide", set())
        requested_attributes = set(attributes or []) if attributes is not None else None

        # An unconditional Hide Field rule is a global UI field restriction.
        # Odoo's Custom Filter, Custom Group By, analytical selectors and
        # Export dialog are driven by fields_get metadata, so mark the field
        # unavailable for those selectors as well as hiding it in view arches.
        global_hidden_metadata = {
            "searchable": False,
            "sortable": False,
            "groupable": False,
            "selectable": False,
            "exportable": False,
            "aggregator": False,
        }
        for field_name in hidden_fields:
            description = result.get(field_name)
            if not description:
                continue
            for key, value in global_hidden_metadata.items():
                if requested_attributes is None or key in requested_attributes:
                    description[key] = value

        for field_name in field_rules.get("no_export", set()):
            if field_name in result:
                result[field_name]["exportable"] = False
        for field_name in field_rules.get("no_import", set()):
            if field_name in result:
                result[field_name]["importable"] = False

        # The Odoo 19 web client obtains Selection dropdown choices from
        # fields_get (including the metadata returned by get_views).
        for field_name, allowed in field_rules.get("allowed_selection", {}).items():
            description = result.get(field_name)
            if description and "selection" in description:
                description["selection"] = [
                    item for item in description["selection"]
                    if str(item[0]) in allowed
                ]
        return result

    # Model-level view-type controls intentionally do not rewrite view arches.
    # They only remove the corresponding choices from Odoo's ControlPanel view
    # switcher in the web client. This avoids blank views and OWL load errors.

    def get_view(self, view_id=None, view_type="form", **options):
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if self.env.context.get("permission_manager_skip_view_hide"):
            return result

        arch = result.get("arch")
        if not arch:
            return result

        model_permission = self.env["permission.manager.model.permission.line"]
        if model_permission._is_model_hidden_for_current_user(self._name):
            if view_type in {"list", "tree"}:
                result["arch"] = (
                    '<list string="Hidden by Access Management" '
                    'create="0" edit="0" delete="0" import="0" '
                    'export_xlsx="0"/>'
                )
            elif view_type == "form":
                result["arch"] = (
                    '<form string="Hidden by Access Management" '
                    'create="0" edit="0" delete="0"><sheet/></form>'
                )
            elif view_type == "kanban":
                result["arch"] = '<kanban create="0" edit="0" delete="0"/>'
            return result

        blocked_ops = self._permission_manager_blocked_operations()
        field_rules = self._permission_manager_field_rules()
        field_state_rules = self._permission_manager_field_state_rules()
        hidden_bindings = self.env[
            "permission.manager.model.permission.line"
        ]._get_hidden_bindings_for_current_user(self._name)
        hidden_view_ids = hidden_bindings.get("views", set())

        if view_id and view_id in hidden_view_ids:
            root_tag = "form" if view_type == "form" else "list"
            result["arch"] = "<%s string='Hidden by Access Management'/>" % root_tag
            return result

        should_process_buttons_tabs = view_type == "form"
        chatter_flags = {}
        if view_type == "form":
            chatter_flags = self.env[
                "permission.manager.chatter.visibility.line"
            ]._get_flags_for_current_user(self._name)
        if (
            not blocked_ops
            and not any(
                field_rules.get(key)
                for key in ("hide", "readonly", "required")
            )
            and not field_state_rules
            and not field_rules.get("allowed_related")
            and not hidden_view_ids
            and not should_process_buttons_tabs
            and not any(chatter_flags.values())
        ):
            return result

        try:
            root = etree.fromstring(arch.encode("utf-8"))
        except etree.XMLSyntaxError:
            return result

        changed = False
        # Combine the allowed-record filter with existing field domains rather
        # than replacing the view's own domain. Nested one2many forms/lists
        # belong to a different model and must be evaluated independently.
        nested_rule_cache = {self._name: field_rules.get("allowed_related", {})}

        def _apply_related_domains(node, model_name):
            nonlocal changed
            if model_name not in self.env.registry:
                return
            model = self.env[model_name]
            if model_name not in nested_rule_cache:
                nested_rule_cache[model_name] = model._permission_manager_field_rules().get(
                    "allowed_related", {}
                )
            rules = nested_rule_cache[model_name]
            for child in node:
                if child.tag != "field" or not child.get("name"):
                    _apply_related_domains(child, model_name)
                    continue
                name = child.get("name")
                field = model._fields.get(name)
                if field and field.type == "many2one" and name in rules:
                    allowed_ids = sorted(rules[name])
                    restriction = "[('id', 'in', %s)]" % repr(allowed_ids)
                    old_domain = child.get("domain")
                    child.set(
                        "domain",
                        "(%s) + (%s)" % (restriction, old_domain)
                        if old_domain else restriction,
                    )
                    changed = True
                if field and field.type in {"one2many", "many2many"}:
                    for embedded in child:
                        if embedded.tag in {"form", "list", "tree", "kanban"}:
                            _apply_related_domains(embedded, field.comodel_name)
                else:
                    _apply_related_domains(child, model_name)

        _apply_related_domains(root, self._name)
        if blocked_ops:
            attr_map = {
                "create": "create",
                "write": "edit",
                "unlink": "delete",
                "copy": "duplicate",
                "import": "import",
                "export": "export_xlsx",
            }
            for operation, attr_name in attr_map.items():
                if operation in blocked_ops:
                    root.set(attr_name, "0")
                    changed = True
            if "hide_action_menu" in blocked_ops:
                for attr_name in (
                    "archive",
                    "delete",
                    "duplicate",
                    "export_xlsx",
                    "import",
                ):
                    root.set(attr_name, "0")
                    changed = True
            if "read" in blocked_ops:
                root.set("invisible", "1")
                changed = True

        if field_rules:
            view_key = "list" if view_type == "tree" else view_type
            field_apply_map = field_rules.get("apply", {})
            globally_hidden_fields = field_rules.get("hide", set())

            # Hide Field + an empty condition is intentionally global.  It does
            # not depend on Apply On: the field disappears from every supported
            # UI view and fields_get metadata removes it from Filter, Group By,
            # Pivot/Graph selectors and Export.
            for field_node in list(root.xpath(".//field[@name]")):
                field_name = field_node.get("name")
                if field_name in globally_hidden_fields:
                    if view_key in {"search", "pivot", "graph"}:
                        parent = field_node.getparent()
                        if parent is not None:
                            parent.remove(field_node)
                    else:
                        field_node.set("invisible", "1")
                        field_node.set("readonly", "1")
                        if view_key in {"list", "tree"}:
                            field_node.set("column_invisible", "1")
                    changed = True
                    continue

                apply_views = field_apply_map.get(field_name, set())
                if view_key not in apply_views:
                    continue
                if field_name in field_rules.get("readonly", set()):
                    field_node.set("readonly", "1")
                    changed = True
                if field_name in field_rules.get("required", set()):
                    field_node.set("required", "1")
                    changed = True

            if view_key == "search" and globally_hidden_fields:
                # Remove predefined filters/group-bys that directly reference a
                # globally hidden field. Custom Filter/Group By field pickers are
                # handled by fields_get(searchable/groupable=False).
                def _references_hidden_field(value):
                    if not value:
                        return False
                    try:
                        tree = ast.parse(value, mode="eval")
                    except (SyntaxError, ValueError, TypeError):
                        return any(
                            "'%s'" % field_name in value
                            or '"%s"' % field_name in value
                            for field_name in globally_hidden_fields
                        )
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Constant) or not isinstance(
                            node.value, str
                        ):
                            continue
                        token = node.value.split(":", 1)[0].split(".", 1)[0]
                        if token in globally_hidden_fields:
                            return True
                    return False

                for filter_node in list(root.xpath(".//filter")):
                    if any(
                        _references_hidden_field(filter_node.get(attribute))
                        for attribute in ("domain", "filter_domain", "context")
                    ):
                        parent = filter_node.getparent()
                        if parent is not None:
                            parent.remove(filter_node)
                            changed = True

        if field_state_rules:
            view_key = "list" if view_type == "tree" else view_type
            for field_node in root.xpath(".//field[@name]"):
                field_name = field_node.get("name")
                for rule in field_state_rules:
                    if field_name != rule["field"] or view_key not in rule["apply"]:
                        continue
                    attribute = rule["attribute"]
                    expression = rule["expression"]
                    current = field_node.get(attribute)
                    if current and current not in {"0", "False", "false"}:
                        expression = "(%s) or (%s)" % (current, expression)
                    field_node.set(attribute, expression)
                    changed = True

                    # A readonly x2many field can still contain object/action buttons
                    # in its embedded list/form architecture. Odoo does not disable
                    # those buttons automatically, so keep them under the same
                    # conditional readonly rule.
                    field = self._fields.get(field_name)
                    if (
                        attribute == "readonly"
                        and field
                        and field.type in {"one2many", "many2many"}
                    ):
                        try:
                            expression_tree = ast.parse(expression, mode="eval")

                            class ParentFieldTransformer(ast.NodeTransformer):
                                def visit_Name(self, node):
                                    if node.id in self_model_fields:
                                        return ast.copy_location(
                                            ast.Attribute(
                                                value=ast.Name(
                                                    id="parent",
                                                    ctx=ast.Load(),
                                                ),
                                                attr=node.id,
                                                ctx=node.ctx,
                                            ),
                                            node,
                                        )
                                    return node

                            self_model_fields = set(self._fields)
                            parent_tree = ParentFieldTransformer().visit(
                                expression_tree
                            )
                            ast.fix_missing_locations(parent_tree)
                            nested_expression = ast.unparse(parent_tree.body)
                        except (SyntaxError, ValueError):
                            nested_expression = expression

                        for button in field_node.xpath(".//button"):
                            button_expression = nested_expression
                            current_button = button.get("invisible")
                            if (
                                current_button
                                and current_button not in {"0", "False", "false"}
                            ):
                                button_expression = "(%s) or (%s)" % (
                                    current_button,
                                    nested_expression,
                                )
                            button.set("invisible", button_expression)
                            changed = True

        if should_process_buttons_tabs:
            keys = self.env[
                "permission.manager.hide.button.tab.line"
            ]._get_hidden_item_keys_for_current_user(self._name)
            if keys["button"] or keys["tab"]:
                item_model = self.env["permission.manager.hide.item"]
                for button in root.xpath(".//button"):
                    key = item_model._make_button_key(button)
                    expression = keys["button"].get(key)

                    # Some inherited/compiled views can add or translate the
                    # button string even when the source button was defined
                    # only with title/icon. Access Management stores the
                    # source key, so an exact key comparison can miss the
                    # rendered button. For named buttons, safely fall back to
                    # type + technical method name when either side has no
                    # string. This keeps the mechanism generic and does not
                    # require a dependency on the module that added the button.
                    if not expression:
                        button_type = button.get("type") or ""
                        button_name = button.get("name") or ""
                        button_string = button.get("string") or ""
                        if button_name:
                            for hidden_key, hidden_expression in keys["button"].items():
                                parts = hidden_key.split(":", 3)
                                if len(parts) != 4 or parts[0] != "button":
                                    continue
                                hidden_type, hidden_name, hidden_string = parts[1:]
                                if (
                                    hidden_type == button_type
                                    and hidden_name == button_name
                                    and (not hidden_string or not button_string)
                                ):
                                    expression = hidden_expression
                                    break

                    if expression:
                        # A button inside an embedded one2many/many2many list is
                        # evaluated against the line record. Hide-button rules,
                        # however, are configured on the parent form model.
                        # Prefix parent-model fields (state, company_id, etc.)
                        # with ``parent.`` so state/domain conditions work for
                        # nested line buttons such as "Duplicate Line".
                        if button.xpath("ancestor::list | ancestor::tree"):
                            try:
                                expression_tree = ast.parse(expression, mode="eval")

                                class ParentButtonFieldTransformer(ast.NodeTransformer):
                                    def visit_Name(self, node):
                                        if node.id in self_model_fields:
                                            return ast.copy_location(
                                                ast.Attribute(
                                                    value=ast.Name(
                                                        id="parent",
                                                        ctx=ast.Load(),
                                                    ),
                                                    attr=node.id,
                                                    ctx=node.ctx,
                                                ),
                                                node,
                                            )
                                        return node

                                self_model_fields = set(self._fields)
                                parent_tree = ParentButtonFieldTransformer().visit(
                                    expression_tree
                                )
                                ast.fix_missing_locations(parent_tree)
                                expression = ast.unparse(parent_tree.body)
                            except (SyntaxError, ValueError):
                                pass

                        current = button.get("invisible")
                        if current and current not in {"0", "False", "false"}:
                            expression = "(%s) or (%s)" % (current, expression)
                        button.set("invisible", expression)
                        changed = True
                for page in root.xpath(".//page"):
                    key = item_model._make_tab_key(page)
                    expression = keys["tab"].get(key)
                    if expression:
                        current = page.get("invisible")
                        if current and current not in {"0", "False", "false"}:
                            expression = "(%s) or (%s)" % (current, expression)
                        page.set("invisible", expression)
                        changed = True

        if chatter_flags and any(chatter_flags.values()):
            for chatter in root.xpath(".//chatter"):
                if chatter_flags.get("hide_chatter"):
                    parent = chatter.getparent()
                    if parent is not None:
                        parent.remove(chatter)
                        changed = True
                else:
                    css_classes = (chatter.get("class") or "").split()
                    class_map = {
                        "hide_composer": "pm_hide_chatter_composer",
                        "hide_log_note": "pm_hide_chatter_log_note",
                        "hide_schedule_activity": "pm_hide_chatter_activity",
                        "hide_search_messages": "pm_hide_chatter_search",
                        "hide_attachments": "pm_hide_chatter_attachments",
                        "hide_followers": "pm_hide_chatter_followers",
                        "hide_follow_button": "pm_hide_chatter_follow_button",
                    }
                    for flag, css_class in class_map.items():
                        if chatter_flags.get(flag) and css_class not in css_classes:
                            css_classes.append(css_class)
                    chatter.set("class", " ".join(css_classes))
                    changed = True

        if changed:
            result["arch"] = etree.tostring(root, encoding="unicode")
        return result


class PermissionManagerAllowedRelatedRecord(models.Model):
    _name = "permission.manager.allowed.related.record"
    _description = "Allowed Related Record for Field Value Filter"
    _order = "id"

    rule_id = fields.Many2one(
        "permission.manager.field.permission.line",
        string="Field Control", required=True, ondelete="cascade", index=True,
    )
    relation_model = fields.Char(
        string="Related Model", required=True, readonly=True,
    )
    record_id = fields.Many2oneReference(
        string="Allowed Record", model_field="relation_model", required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        values = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("rule_id"):
                rule = self.env["permission.manager.field.permission.line"].browse(
                    vals["rule_id"]
                )
                vals["relation_model"] = rule.field_id.relation
            values.append(vals)
        return super().create(values)

    @api.constrains("rule_id", "relation_model", "record_id")
    def _check_allowed_record(self):
        for item in self:
            field = item.rule_id.field_id
            if (
                not field or field.ttype != "many2one"
                or item.relation_model != field.relation
                or not item.record_id
            ):
                raise UserError(
                    _("Allowed Record must match the Field Control's Many2one model.")
                )
            if not self.env[item.relation_model].sudo().browse(item.record_id).exists():
                raise UserError(_("The selected Allowed Record does not exist."))



class IrActionsActions(models.Model):
    _inherit = "ir.actions.actions"

    def get_bindings(self, model_name):
        result = super().get_bindings(model_name)
        hidden = self.env[
            "permission.manager.model.permission.line"
        ]._get_hidden_bindings_for_current_user(model_name)
        hidden_reports = hidden.get("reports", set())
        hidden_actions = hidden.get("actions", set())
        hide_action_menu = hidden.get("hide_action_menu")
        if hide_action_menu:
            if isinstance(result, dict):
                result = dict(result)
                result["action"] = []
            return result
        if not hidden_reports and not hidden_actions:
            return result

        def _filter(items, hidden_ids):
            clean_items = []
            for item in items or []:
                item_id = item.get("id") if isinstance(item, dict) else False
                if item_id not in hidden_ids:
                    clean_items.append(item)
            return clean_items

        if isinstance(result, dict):
            result = dict(result)
            result["report"] = _filter(result.get("report"), hidden_reports)
            result["action"] = _filter(result.get("action"), hidden_actions)
        return result



class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _visible_menu_ids(self, *args, **kwargs):
        visible_menu_ids = super()._visible_menu_ids(*args, **kwargs)
        hidden_menu_ids = self.env[
            "permission.manager.hidden.menu.line"
        ]._get_hidden_menu_ids_for_current_user()
        hidden_models = self.env[
            "permission.manager.model.permission.line"
        ]._get_hidden_model_names_for_current_user()
        if hidden_models:
            menus = self.sudo().browse(list(visible_menu_ids)).exists()
            for menu in menus:
                action = menu.action
                if action and getattr(action, "res_model", False) in hidden_models:
                    hidden_menu_ids.add(menu.id)
        if not hidden_menu_ids:
            return visible_menu_ids
        if isinstance(visible_menu_ids, set):
            return visible_menu_ids - hidden_menu_ids
        if isinstance(visible_menu_ids, frozenset):
            return frozenset(set(visible_menu_ids) - hidden_menu_ids)
        return [menu_id for menu_id in visible_menu_ids if menu_id not in hidden_menu_ids]

class ResUsers(models.Model):
    _inherit = "res.users"

    def write(self, vals):
        result = super().write(vals)
        if {"group_ids", "company_id", "company_ids", "active"}.intersection(vals):
            self.env[
                "permission.manager.policy"
            ]._clear_permission_manager_menu_cache()
        return result

    def _check_credentials(self, *args, **kwargs):
        """Block login for users matched by an active Access Management policy.

        The check is done after Odoo validates the password but before the login
        is accepted.  This avoids overriding ``_login`` directly, whose
        signature can differ between Odoo 19 builds and can cause Internal
        Server Error during authentication.
        """
        result = super()._check_credentials(*args, **kwargs)
        for user in self:
            is_blocked = self.env[
                "permission.manager.policy"
            ].sudo()._is_login_blocked_for_user(user.id)
            if is_blocked:
                raise AccessDenied(
                    _("Login is blocked by Access Management policy.")
                )
        return result

