import json
from odoo import http
from odoo.http import request, Response
import logging

_logger = logging.getLogger(__name__)

class BkashController(http.Controller):

    @http.route('/payment/bkash/return', type='http', auth='public', csrf=False, sitemap=False)
    def bkash_return(self, **kw):
        """
        bKash will hit this URL (server-to-server and/or browser redirect) with:
          - reference: our original tx reference (we included it in callbackURL)
          - statusCode: '0000' => success, '9999' => failure or cancel
          - paymentID: bKash payment id (optional but useful)
        """
        reference = kw.get('reference')
        status_code = kw.get('statusCode') or kw.get('status_code') or ''
        payment_id = kw.get('paymentID') or kw.get('paymentId')

        if not reference:
            return Response(json.dumps({"error": "Missing reference"}), 400,
                            [('Content-Type', 'application/json; charset=utf-8')])

        tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        if not tx:
            return Response(json.dumps({"error": "Transaction not found"}), 404,
                            [('Content-Type', 'application/json; charset=utf-8')])

        try:
            if payment_id and not tx.bkash_payment_id:
                tx.write({"bkash_payment_id": payment_id})

            # Interpret statusCode per your rule
            if status_code == '0000':
                tx._set_done()
                next_url = '/shop/confirmation'
            elif status_code == '9999':
                tx._set_canceled("bKash reported failure/cancel")
                next_url = '/shop/payment'
            else:
                # Fallback: unknown/missing statusCode
                tx._set_canceled(f"Unknown bKash statusCode: {status_code or 'missing'}")
                next_url = '/shop/payment'

            request.env.cr.commit()
            return request.redirect(next_url, code=303)

        except Exception as e:
            _logger.exception("Error processing bKash callback for %s", reference)
            request.env.cr.rollback()
            return Response(json.dumps({"error": f"Callback processing failed: {e}"}), 500,
                            [('Content-Type', 'application/json; charset=utf-8')])
