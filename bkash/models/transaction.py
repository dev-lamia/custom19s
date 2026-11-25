import json
import logging
from urllib.parse import quote_plus  # Replace html.escape with this
import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request, Response
from odoo import http

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    bkash_payment_id = fields.Char(readonly=True, copy=False)
    # ---- URL helpers (per-request, no globals) ----
    def _bkash_base(self) -> str:
        self.ensure_one()
        state = self.provider_id.state
        if state == 'test':
            # sandbox base (bka.sh)
            return "https://tokenized.sandbox.bka.sh/v1.2.0-beta"
        elif state == 'enabled':
            # production base (bka.sh)
            return "https://tokenized.pay.bka.sh/v1.2.0-beta"
        raise ValidationError("Invalid payment provider state!")

    def _bkash_urls(self) -> dict:
        root = f"{self._bkash_base()}/tokenized/checkout"
        return {
            "grant":   f"{root}/token/grant",
            "create":  f"{root}/create",
            "execute": f"{root}/execute",
        }
    def _get_specific_processing_values(self, processing_values):
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'bkash':
            return res
        self.ensure_one()
        base = self.provider_id.get_base_url().replace('localhost', '127.0.0.1').rstrip('/')
        # Use quote_plus for proper URL encoding
        callback_url = f"{base}/payment/bkash/return?reference={quote_plus(self.reference)}"

        try:
            token = self._bkash_grant_token()
            create_payload = self._bkash_build_create_payload(callback_url)
            create_resp = self._bkash_create_payment(token, create_payload)
        except Exception as e:
            _logger.exception("bKash create flow failed for reference %s", self.reference)
            raise ValidationError(f"bKash payment initialization failed: {e}")

        payment_id = create_resp.get("paymentID") or create_resp.get("paymentId")
        bkash_url  = (create_resp.get("bkashURL") or "").strip()
        if not payment_id or not bkash_url:
            _logger.error("bKash create response missing paymentID/URL: %s", create_resp)
            raise ValidationError("bKash did not return paymentID/bkashURL.")
        

        
        res['force_flow'] = 'redirect'
        res['api_url'] = bkash_url

        res['redirect_form'] = {
            'url': bkash_url,
            'method': 'post',
            'inputs': {},  
        }

        # res['redirect_form_html'] = '<form id="o_payment_redirect_form"></form>'
        res['redirect_form_html'] = (
            f'<form id="o_payment_redirect_form" action="{bkash_url}" method="post">'
            '</form>'
            '<script>document.getElementById("o_payment_redirect_form").submit();</script>'
        )

        return res

    # ---- bKash API helpers ----
    def _bkash_grant_token(self):
        icp = self.env['ir.config_parameter'].sudo()
        app_key = icp.get_param('payment_bkash.app_key')
        app_secret = icp.get_param('payment_bkash.app_secret')
        username = icp.get_param('payment_bkash.username')
        password = icp.get_param('payment_bkash.password')
        if not all([app_key, app_secret, username, password]):
            raise ValidationError("bKash credentials missing in system parameters.")
        urls = self._bkash_urls()
        payload = {"app_key": app_key, "app_secret": app_secret}
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'username': username,
            'password': password,
        }
        r = requests.post(urls["grant"], headers=headers, data=json.dumps(payload), timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code != 200:
            raise ValidationError(f"Grant token HTTP {r.status_code}: {r.text}")
        if data.get("statusCode") != "0000" or not data.get("id_token"):
            raise ValidationError(f"Grant token failed: {data}")
        return data["id_token"]
    
    # Bkash Create Payment
    
    def _bkash_build_create_payload(self, callback_url: str):
        amount_str = f"{self.amount:.2f}"
        currency = (self.currency_id and self.currency_id.name) or "BDT"
        payer_ref = str(self.partner_id.id or "1")
        return {
            "mode": "0011",
            "payerReference": payer_ref,
            "callbackURL": callback_url,   
            "amount": amount_str,
            "currency": currency,
            "intent": "sale",
            "merchantInvoiceNumber": self.reference,
        }

    def _bkash_create_payment(self, id_token: str, payload: dict):
        app_key = self.env['ir.config_parameter'].sudo().get_param('payment_bkash.app_key')
        urls = self._bkash_urls()
        headers = {
            'X-APP-Key': app_key or '',
            'accept': 'application/json',
            'content-type': 'application/json',
            'Authorization': f'Bearer {id_token}',
        }
        r = requests.post(urls["create"], headers=headers, data=json.dumps(payload), timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code != 200:
            raise ValidationError(f"Create payment HTTP {r.status_code}: {r.text}")
        if data.get("statusCode") != "0000" or not data.get("bkashURL"):
            raise ValidationError(f"Create payment failed: {data}")
        return data
    
    def _bkash_execute_payment(self, id_token: str, payment_id: str):
        """Call bKash execute with the given paymentID."""
        self.ensure_one()
        app_key = self.env['ir.config_parameter'].sudo().get_param('payment_bkash.app_key') or ''
        urls = self._bkash_urls()
        headers = {
            'Authorization': f'Bearer {id_token}',
            'X-APP-Key': app_key,
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        payload = {'paymentID': payment_id}
        r = requests.post(urls["execute"], headers=headers, data=json.dumps(payload), timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {}
        # We do NOT raise here; we return the payload so the controller can decide
        return r.status_code, data
   
    def _bkash_update_sale_orders(self, success: bool):
        """Confirm or cancel linked sale orders based on the result."""
        self.ensure_one()
        # Preferred: rely on relation set by website_sale/payment
        orders = self.sudo().sale_order_ids
        # Fallback: try to locate by base SO name if needed
        if not orders and self.reference:
            base_name = self.reference.split('-')[0]
            orders = self.env['sale.order'].sudo().search([('name', '=', base_name)])
        if not orders:
            return

        if success:
            for so in orders:
                if so.state in ('draft', 'sent'):
                    so.action_confirm()
        