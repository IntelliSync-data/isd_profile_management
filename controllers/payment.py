# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentController(http.Controller):

    @http.route('/isd_profile_management/payment/ipn', type='http', auth='public', methods=['GET'], csrf=False)
    def ipn_receiver(self, **kwargs):
        """
        IPN endpoint for redirect-based payment providers (VTCPay, PayPal).
        Verifies the payment via the isd_payment REST API and confirms the profile payment.
        """

        # Get query parameters
        query_params = dict()
        if request.httprequest.args:
            query_params = dict(request.httprequest.args)

        if not query_params:
            raise ValueError("No query parameters found in IPN request")

        # Determine transaction_id from query params
        # VTCPay sends reference_number; PayPal sends token
        transaction_id: str = (
            query_params.get("reference_number")
            or query_params.get("token")
            or ""
        )

        if not transaction_id:
            raise ValueError("Could not determine transaction_id from IPN query parameters")

        payment_record = request.env['profile.payment'].sudo().search(
            [('transaction_id', '=', transaction_id)], limit=1)
        if not payment_record:
            raise ValueError(
                f"No payment record found for transaction_id: {transaction_id}")

        # Delegate verification and confirmation to action_check_payment_status
        # which calls the isd_payment REST API
        result = payment_record.action_check_payment_status()

        if result.get('status') != 'confirmed':
            raise ValueError(
                f"Payment not confirmed for transaction_id: {transaction_id}, "
                f"status: {result.get('status')}, message: {result.get('message')}"
            )

        user_profile = payment_record.user_profile_id
        metadata = payment_record.metadata or {}
        action_id = metadata.get("action_id")

        return request.redirect(
            "/web#action={}&model=user.profile&view_type=form&id={}".format(
                action_id, user_profile.id if user_profile else ""
            )
        )

    @http.route('/isd_profile_management/payment/ipn', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def ipn_options(self, **kwargs):
        """Handle CORS preflight requests for all HTTP methods"""
        return request.make_response(
            "",
            status=200,
            headers=[
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods',
                 'GET, POST, PUT, DELETE, PATCH, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            ]
        )

    @http.route('/isd_profile_management/payment/check', type='http', auth='user', methods=['POST'], csrf=False)
    def check_payment(self, **post):
        """HTTP JSON endpoint polled by the frontend to confirm payment status for a transaction_id.

        Accepts a plain JSON body {transaction_id: '...'} or form-encoded POST.
        Returns application/json with {success, status, message}.
        """
        # Read JSON body (handle different request types)
        data = {}
        try:
            # Preferred: request.jsonrequest works when content-type is application/json
            data = request.jsonrequest or {}
        except Exception:
            try:
                raw = request.httprequest.get_data(as_text=True)
                if raw:
                    data = json.loads(raw)
            except Exception:
                data = {}

        # Merge kwargs/post form into data as fallback
        if post:
            data.update(post)

        transaction_id = data.get('transaction_id') or data.get(
            'transactionId') or None
        if not transaction_id:
            resp = {'success': False, 'error': 'missing_transaction_id'}
            return request.make_response(json.dumps(resp), headers=[('Content-Type', 'application/json')])

        payment = request.env['profile.payment'].sudo().search(
            [('transaction_id', '=', transaction_id)], limit=1)
        if not payment:
            resp = {'success': False, 'error': 'payment_not_found'}
            return request.make_response(json.dumps(resp), headers=[('Content-Type', 'application/json')])

        try:
            result = payment.sudo().action_check_payment_status()

            status = result.get('status', 'processing')
            message = result.get('message', 'Payment status unknown')

            if status == 'confirmed':
                resp = {
                    'success': True,
                    'status': 'confirmed',
                    'message': message
                }
            elif status == 'expired':
                resp = {
                    'success': False,
                    'status': 'expired',
                    'message': message
                }
            else:
                resp = {
                    'success': True,
                    'status': 'pending',
                    'message': message
                }

            return request.make_response(json.dumps(resp), headers=[('Content-Type', 'application/json')])
        except Exception as e:
            _logger.exception('Error while checking payment status')
            resp = {'success': False, 'error': str(e)}
            return request.make_response(json.dumps(resp), headers=[('Content-Type', 'application/json')])
