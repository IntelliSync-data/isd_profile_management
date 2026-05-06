# -*- coding: utf-8 -*-

import json
import logging
import os
from ..models.services.payment_service import PAYPAL_PROVIDER, VTC_PAY_PROVIDER, ConfirmPGPaymentResDto
from odoo import http, fields
from odoo.http import request
from concurrent.futures import ThreadPoolExecutor
import time
from ..models.user_profile import ConfirmPGPaymentReqDto, PaymentService, PaymentServiceFactory

_logger = logging.getLogger(__name__)

# Dynamic base URL configuration - no more hard-coding


class PaymentController(http.Controller):

    @http.route('/isd_profile_management/payment/ipn', type='http', auth='public', methods=['GET'], csrf=False)
    def ipn_receiver(self, **kwargs):
        """
        Universal IPN endpoint to receive any HTTP method and store all request data
        Responds with HTTP 200 OK status
        """

        # Get query parameters - always separate from body
        query_params = dict()
        if request.httprequest.args:
            query_params = dict(request.httprequest.args)

        if not query_params:
            raise ValueError("No query parameters found in IPN request")
        
        merchant: str = query_params.get('merchant', '').lower() or VTC_PAY_PROVIDER

        transaction_id: str = ""
        if merchant == VTC_PAY_PROVIDER:
            transaction_id = query_params["reference_number"]
        elif merchant == PAYPAL_PROVIDER:
            transaction_id = query_params["token"]

        payment_record = request.env['profile.payment'].sudo().search(
            [('transaction_id', '=', transaction_id)], limit=1)
        if not payment_record:
            raise ValueError(
                f"No payment record found for transaction_id: {transaction_id}")

        # Process the payment record (e.g., update status, log, etc.)
        payment_service: PaymentService = PaymentServiceFactory.create(
            provider=merchant, env=request.env)

        confirm_dto = ConfirmPGPaymentReqDto(amount=payment_record.amount)
        if merchant == VTC_PAY_PROVIDER:
            confirm_dto.payment_parameters = "&".join(
                [f"{k}={v}" for k, v in query_params.items()])
        res_dto = payment_service.confirm_payment(transaction_id, confirm_dto)
        
        if res_dto.status != str(ConfirmPGPaymentResDto.Status.ACTIVE):
            raise ValueError(
                f"Payment not confirmed for transaction_id: {transaction_id}, status: {res_dto.status}")
        
        payment_record.write({
            'state': 'confirmed',
        })
        user_profile = payment_record.user_profile_id
        if user_profile:
            user_profile.write({'state': 'paid'})

        metadata = payment_record.metadata or {}
        action_id = metadata.get("action_id")

        # Return HTTP 200 OK status (no text content)
        # lesson_url = os.getenv("BASE_URL", "")
        return request.redirect("/web#action={}&model=user.profile&view_type=form&id={}".format(action_id, user_profile.id))

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
            # Determine provider if stored in metadata, otherwise fallback to sepay
            provider = None
            # Use new ISD Payment integration
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
