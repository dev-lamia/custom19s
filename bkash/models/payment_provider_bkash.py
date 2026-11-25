from odoo import fields, models,api

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('bkash', "Bkash")],
        ondelete={'bkash': 'set default'},
    )

    def _get_journal_inbound_payment_method_line(self):
        """Return an inbound payment method line; auto-provision for bKash if missing."""
        line = super()._get_journal_inbound_payment_method_line()
        if line or any(p.code != 'bkash' for p in self):
            return line

        for provider in self.filtered(lambda p: p.code == 'bkash'):
            journal = provider.journal_id or self.env['account.journal'].search([
                ('type', 'in', ['bank', 'cash']),
                ('company_id', '=', provider.company_id.id),
            ], limit=1)
            if not journal:
                journal = self.env['account.journal'].create({
                    'name': 'bKash',
                    'code': 'BKSH',
                    'type': 'bank',
                    'company_id': provider.company_id.id,
                })
            # reuse hook’s helper logic
            method_in = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False) \
                        or self.env['account.payment.method'].search(
                            [('payment_type', '=', 'inbound'), ('code', 'in', ['manual', 'manual_in'])],
                            limit=1)
            pml = self.env['account.payment.method.line'].search(
                [('journal_id', '=', journal.id), ('payment_type', '=', 'inbound')], limit=1)
            if not pml:
                pml = self.env['account.payment.method.line'].create({
                    'name': 'bKash Inbound',
                    'journal_id': journal.id,
                    'payment_method_id': method_in.id,
                    'payment_type': 'inbound',
                })
            provider.journal_id = journal.id
            line |= pml
        return line

    _bkash_company_dependent = True  # keep True if you want per-company values

    bkash_app_key = fields.Char(
        string="bKash App Key",
        compute="_compute_bkash_params",
        inverse="_inverse_bkash_app_key",
        readonly=False,
    )
    bkash_app_secret = fields.Char(
        string="bKash App Secret",
        compute="_compute_bkash_params",
        inverse="_inverse_bkash_app_secret",
        readonly=False,
    )
    bkash_username = fields.Char(
        string="bKash Username",
        compute="_compute_bkash_params",
        inverse="_inverse_bkash_username",
        readonly=False,
    )
    bkash_password = fields.Char(
        string="bKash Password",
        compute="_compute_bkash_params",
        inverse="_inverse_bkash_password",
        readonly=False,
    )

    # --- FIX: use fixed keys (no provider.id in the name)
    def _bkash_param_keys(self):
        return {
            "app_key":    "payment_bkash.app_key",
            "app_secret": "payment_bkash.app_secret",
            "username":   "payment_bkash.username",
            "password":   "payment_bkash.password",
        }

    def _bkash_param_env(self):
        params = self.env['ir.config_parameter'].sudo()
        if self._bkash_company_dependent:
            return params.with_company(self.company_id or self.env.company)
        return params

    @api.depends('company_id')  # do NOT depend on 'id'
    def _compute_bkash_params(self):
        for provider in self:
            keys = provider._bkash_param_keys()
            params = provider._bkash_param_env()
            provider.bkash_app_key    = params.get_param(keys["app_key"], default=False)
            provider.bkash_app_secret = params.get_param(keys["app_secret"], default=False)
            provider.bkash_username   = params.get_param(keys["username"], default=False)
            provider.bkash_password   = params.get_param(keys["password"], default=False)

    def _inverse_bkash_app_key(self):
        keys = self._bkash_param_keys()
        for provider in self:
            provider._bkash_param_env().set_param(keys["app_key"], provider.bkash_app_key or "")

    def _inverse_bkash_app_secret(self):
        keys = self._bkash_param_keys()
        for provider in self:
            provider._bkash_param_env().set_param(keys["app_secret"], provider.bkash_app_secret or "")

    def _inverse_bkash_username(self):
        keys = self._bkash_param_keys()
        for provider in self:
            provider._bkash_param_env().set_param(keys["username"], provider.bkash_username or "")

    def _inverse_bkash_password(self):
        keys = self._bkash_param_keys()
        for provider in self:
            provider._bkash_param_env().set_param(keys["password"], provider.bkash_password or "")
