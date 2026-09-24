# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ExternalProfileAPIController(http.Controller):
    """
    External API controller for profile package creation and payment confirmation
    For external websites that don't have user login
    """

    @http.route('/api/profile/package-info', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def get_package_info(self, **kwargs):
        try:
            package_id = kwargs.get('package_id')
            if not package_id:
                return {
                    'success': False,
                    'error': 'Package ID is required',
                    'error_code': 'MISSING_PACKAGE_ID'
                }

            package = request.env['profile.management'].sudo().browse(package_id)
            if not package.exists():
                return {
                    'success': False,
                    'error': 'Package not found',
                    'error_code': 'PACKAGE_NOT_FOUND'
                }

            active_steps = package.step_ids.filtered(lambda s: s.state == 'active')

            # Same list the Odoo checkout popup offers, so both stay in sync:
            # live methods for a Live package, test methods for a Demo one
            methods = request.env['payment.method.select.wizard'].sudo()._get_available_methods(package)
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

            return {
                'success': True,
                'payment_methods': [{
                    'id': method.id,
                    'name': method.name,
                    'type': method.payment_provider or '',
                    # guarded: isd_payment may still be running a version without them
                    'description': (method.description or '') if 'description' in method._fields else '',
                    'environment': (method.environment or '') if 'environment' in method._fields else '',
                    'image_url': f"{base_url}/web/image/isd_payment.method/{method.id}/image" if method.image else '',
                } for method in methods],
                'package': {
                    'id': package.id,
                    'name': package.name,
                    'description': package.description or '',
                    'state': package.state,
                    'package_cost': package.package_cost,
                    'use_promotional_price': package.use_promotional_price,
                    'promotional_cost': package.promotional_cost,
                    'total_cost': package.total_cost,
                    'total_cost_display': package.total_cost_display,
                    'services': [{
                        'id': step.id,
                        'name': step.name,
                        'cost': step.cost,
                    } for step in active_steps],
                }
            }

        except Exception as e:
            _logger.exception("Error getting package info via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }

    @http.route('/api/profile/create', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def create_profile_package(self, **kwargs):
        """
        Create profile package for external user

        Input JSON:
        {
            "package_id": 123,
            "email": "user@example.com",
            "name": "Nguyen Van A",  (optional)
            "phone": "0901234567",  (optional)
            "notes": "Customer info: Name, Phone, Address",
            "address": "123 Nguyen Hue, District 1, Ho Chi Minh City",  (optional)
            "payment_method_id": 1
        }

        Output JSON:
        {
            "success": true,
            "user_profile_id": 456,
            "transaction_id": "TEST_ABC123",
            "qr_url": "https://...",
            "amount": 2000000
        }
        """
        try:
            # Get input parameters
            package_id = kwargs.get('package_id')
            email = kwargs.get('email')
            notes = kwargs.get('notes', '')
            address = kwargs.get('address') or ''
            name = kwargs.get('name') or ''
            phone = kwargs.get('phone') or ''
            payment_method_id = kwargs.get('payment_method_id')
            half_payment = kwargs.get('half_payment', False)

            for label, value, code in (
                ('Address', address, 'INVALID_ADDRESS'),
                ('Name', name, 'INVALID_NAME'),
                ('Phone', phone, 'INVALID_PHONE'),
            ):
                if not isinstance(value, str):
                    return {
                        'success': False,
                        'error': '%s must be a string' % label,
                        'error_code': code
                    }
            name = name.strip()
            phone = phone.strip()

            # Validate input
            if not package_id:
                return {
                    'success': False,
                    'error': 'Package ID is required',
                    'error_code': 'MISSING_PACKAGE_ID'
                }

            if not email:
                return {
                    'success': False,
                    'error': 'Email is required',
                    'error_code': 'MISSING_EMAIL'
                }

            if not payment_method_id:
                return {
                    'success': False,
                    'error': 'Payment Method ID is required',
                    'error_code': 'MISSING_PAYMENT_METHOD_ID'
                }

            # Check if package exists
            package = request.env['profile.management'].sudo().browse(package_id)
            if not package.exists():
                return {
                    'success': False,
                    'error': 'Package not found',
                    'error_code': 'PACKAGE_NOT_FOUND'
                }

            if package.state != 'active':
                return {
                    'success': False,
                    'error': 'Package is not active',
                    'error_code': 'PACKAGE_INACTIVE'
                }

            # Check if payment method exists
            payment_method = request.env['isd_payment.method'].sudo().browse(payment_method_id)
            if not payment_method.exists():
                return {
                    'success': False,
                    'error': 'Payment method not found',
                    'error_code': 'PAYMENT_METHOD_NOT_FOUND'
                }

            # A Demo package must not be paid with a live method, and a Live
            # package must not be paid with a test one
            Wizard = request.env['payment.method.select.wizard'].sudo()
            if payment_method not in Wizard._get_available_methods(package):
                return {
                    'success': False,
                    'error': 'This payment method cannot be used for this package',
                    'error_code': 'PAYMENT_METHOD_NOT_ALLOWED'
                }

            # The website posts full contact details to isd_chatbot's /api/inquiry, so
            # reuse them when this API is called with the email only. Guarded because
            # isd_chatbot is not a dependency of this module.
            if (not name or not phone) and 'customer.inquiry' in request.env:
                inquiry = request.env['customer.inquiry'].sudo().search(
                    [('email', '=', email)], order='id desc', limit=1)
                if inquiry:
                    name = name or inquiry.name or ''
                    phone = phone or inquiry.phone or ''

            # Find or create contact by email
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                partner_vals = {
                    # fall back to the email local part when the caller sends no name
                    'name': name or email.split('@')[0],
                    'email': email,
                }
                if phone:
                    partner_vals['phone'] = phone
                # customer_rank only exists when the 'account' module is installed
                if 'customer_rank' in Partner._fields:
                    partner_vals['customer_rank'] = 1
                partner = Partner.create(partner_vals)
            else:
                # Complete an existing contact without overwriting what it already has
                missing_vals = {}
                if name and (not partner.name or partner.name == email.split('@')[0]):
                    missing_vals['name'] = name
                if phone and not partner.phone:
                    missing_vals['phone'] = phone
                if missing_vals:
                    partner.write(missing_vals)

            # Get all active steps from package
            active_steps = package.step_ids.filtered(lambda s: s.state == 'active')

            # Validate package has steps
            if not active_steps:
                return {
                    'success': False,
                    'error': 'Package has no active steps configured',
                    'error_code': 'NO_STEPS'
                }

            # Calculate and lock total cost at time of order
            if package.use_promotional_price:
                total_amount = package.promotional_cost
            else:
                total_amount = sum(active_steps.mapped('cost')) + (package.package_cost or 0)
            if total_amount <= 0:
                total_amount = package.total_cost or 0

            # Always create a new user profile (each purchase is a separate order)
            user_profile = request.env['user.profile'].sudo().with_context(skip_create_steps=True).create({
                'partner_id': partner.id,
                'profile_id': package.id,
                'state': 'new',
                'assigned_date': fields.Datetime.now(),
                'notes': notes,
                'address': address or False,
                'locked_cost': total_amount,
            })

            # Create user step instances for all steps
            user_step_ids = []
            for step in active_steps:
                user_step = request.env['user.step'].sudo().create({
                    'step_id': step.id,
                    'user_profile_id': user_profile.id,
                    'state': 'not_started',
                    'payment_status': 'not_paid',
                    'is_selected': True,
                    'cost': step.cost,
                })
                user_step_ids.append(user_step.id)

            # Flush to database to ensure user_step records exist
            request.env.cr.flush()

            # Validate total amount
            if total_amount <= 0:
                return {
                    'success': False,
                    'error': 'Package has no cost or all steps are free',
                    'error_code': 'INVALID_AMOUNT'
                }

            # Half payment: pay 50%
            if half_payment:
                total_amount = total_amount / 2

            # Create profile payment (link to user_step records that were just created)
            profile_payment = request.env['profile.payment'].sudo().create({
                'user_profile_id': user_profile.id,
                'partner_id': partner.id,
                'amount': total_amount,
                'step_ids': [(6, 0, user_step_ids)],
                'state': 'draft',
            })

            # Generate QR code via isd_payment integration
            payment_response = profile_payment.with_context(
                payment_method_id=payment_method_id
            ).action_create_isd_payment_external(payment_method)

            # Profile stays in 'new' state, payment_status remains 'not_yet_paid'

            # Send order confirmation email
            user_profile._send_order_confirmation_email(payment=profile_payment)

            # Log creation (but don't send to end user unless enabled)
            user_profile.message_post(
                body=_("Profile created via external API. Email: %s, Notes: %s") % (email, notes),
                message_type='comment',  # Internal note, not sent to user
                subtype_xmlid='mail.mt_note'  # Internal note subtype
            )

            result = {
                'success': True,
                'user_profile_id': user_profile.id,
                'transaction_id': payment_response.get('transaction_id'),
                'amount': total_amount,
            }
            # Include provider-specific response fields
            if payment_response.get('redirect_url'):
                result['redirect_url'] = payment_response['redirect_url']
            if payment_response.get('amount_usd'):
                result['amount_usd'] = payment_response['amount_usd']
            if payment_response.get('qr_url'):
                result['qr_url'] = payment_response['qr_url']
            return result

        except Exception as e:
            _logger.exception("Error creating profile package via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }

    @http.route('/api/profile/confirm-payment', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def confirm_payment(self, **kwargs):
        """
        Confirm payment for profile package

        Input JSON:
        {
            "user_profile_id": 456,
            "transaction_code": "TEST_ABC123"
        }

        Output JSON:
        {
            "success": true,
            "message": "Payment confirmed successfully"
        }
        """
        try:
            # Get input parameters
            user_profile_id = kwargs.get('user_profile_id')
            transaction_code = kwargs.get('transaction_code')

            # Validate input
            if not user_profile_id:
                return {
                    'success': False,
                    'error': 'User Profile ID is required',
                    'error_code': 'MISSING_USER_PROFILE_ID'
                }

            if not transaction_code:
                return {
                    'success': False,
                    'error': 'Transaction code is required',
                    'error_code': 'MISSING_TRANSACTION_CODE'
                }

            # Find user profile
            user_profile = request.env['user.profile'].sudo().browse(user_profile_id)
            if not user_profile.exists():
                return {
                    'success': False,
                    'error': 'User profile not found',
                    'error_code': 'USER_PROFILE_NOT_FOUND'
                }

            # Find payment by user_profile_id and transaction_code
            payment = request.env['profile.payment'].sudo().search([
                ('user_profile_id', '=', user_profile_id),
                ('transaction_id', '=', transaction_code)
            ], limit=1)

            if not payment:
                return {
                    'success': False,
                    'error': 'Payment not found with given transaction code',
                    'error_code': 'PAYMENT_NOT_FOUND'
                }

            # Check if already confirmed
            if payment.state == 'confirmed':
                return {
                    'success': True,
                    'message': 'Payment already confirmed'
                }

            # Confirm payment
            payment.action_confirm()

            return {
                'success': True,
                'message': 'Payment confirmed successfully'
            }

        except Exception as e:
            _logger.exception("Error confirming payment via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }

    def _find_order(self, user_profile_id=None, order_code=None):
        """Resolve an order from its id or from the code the customer sees.

        Returns (user_profile, error_dict); exactly one of them is filled.
        """
        if user_profile_id:
            try:
                user_profile_id = int(user_profile_id)
            except (TypeError, ValueError):
                return None, {
                    'success': False,
                    'error': 'user_profile_id must be an integer',
                    'error_code': 'INVALID_USER_PROFILE_ID'
                }
            user_profile = request.env['user.profile'].sudo().browse(user_profile_id)
        elif order_code:
            payment = request.env['profile.payment'].sudo().search(
                ['|', ('transaction_id', '=', order_code),
                 ('name', '=', order_code)], limit=1)
            user_profile = payment.user_profile_id
        else:
            return None, {
                'success': False,
                'error': 'Either user_profile_id or order_code is required',
                'error_code': 'MISSING_ORDER_REFERENCE'
            }

        if not user_profile or not user_profile.exists():
            return None, {
                'success': False,
                'error': 'Order not found',
                'error_code': 'ORDER_NOT_FOUND'
            }
        return user_profile, None

    @http.route('/api/profile/create-payment', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def create_payment(self, **kwargs):
        """
        Start a new payment on an order that already exists.

        Input JSON:
        {
            "order_code": "BP_XXX",
            "payment_method_id": 3
        }

        `user_profile_id` is accepted in place of `order_code`. Any transaction
        still waiting on this order is cancelled first, so the customer is never
        left with two live QR codes.
        """
        try:
            user_profile, error = self._find_order(
                kwargs.get('user_profile_id'),
                kwargs.get('order_code') or kwargs.get('transaction_code'))
            if error:
                return error

            if user_profile.state == 'cancelled':
                return {
                    'success': False,
                    'error': 'Order is cancelled',
                    'error_code': 'ORDER_CANCELLED'
                }

            if user_profile.payment_status == 'paid':
                return {
                    'success': False,
                    'error': 'Order is already paid',
                    'error_code': 'ALREADY_PAID'
                }

            payment_method_id = kwargs.get('payment_method_id')
            payment_method = request.env['isd_payment.method'].sudo().browse(
                payment_method_id) if payment_method_id else None
            if not payment_method or not payment_method.exists():
                return {
                    'success': False,
                    'error': 'Payment method not found',
                    'error_code': 'PAYMENT_METHOD_NOT_FOUND'
                }

            # Same rule as /api/profile/create: a Demo package must not reach a
            # live gateway
            Wizard = request.env['payment.method.select.wizard'].sudo()
            if payment_method not in Wizard._get_available_methods(user_profile.profile_id):
                return {
                    'success': False,
                    'error': 'This payment method cannot be used for this package',
                    'error_code': 'PAYMENT_METHOD_NOT_ALLOWED'
                }

            # Drop whatever was still waiting, gateway side included
            user_profile._cancel_open_payments()

            amount = user_profile.remaining_amount or user_profile.total_cost
            if amount <= 0:
                return {
                    'success': False,
                    'error': 'Order has nothing left to pay',
                    'error_code': 'INVALID_AMOUNT'
                }

            profile_payment = request.env['profile.payment'].sudo().create({
                'user_profile_id': user_profile.id,
                'partner_id': user_profile.partner_id.id if user_profile.partner_id else False,
                'amount': amount,
                'step_ids': [(6, 0, user_profile.user_step_ids.ids)],
                'state': 'draft',
            })

            payment_response = profile_payment.with_context(
                payment_method_id=payment_method.id
            ).action_create_isd_payment_external(payment_method)

            user_profile.message_post(
                body=_("New payment started via external API: %s") % (
                    payment_response.get('transaction_id') or ''),
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )

            result = {
                'success': True,
                'user_profile_id': user_profile.id,
                'transaction_id': payment_response.get('transaction_id'),
                'amount': amount,
            }
            if payment_response.get('redirect_url'):
                result['redirect_url'] = payment_response['redirect_url']
            if payment_response.get('amount_usd'):
                result['amount_usd'] = payment_response['amount_usd']
            if payment_response.get('qr_url'):
                result['qr_url'] = payment_response['qr_url']
            return result

        except Exception as e:
            _logger.exception("Error creating a payment via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }

    @http.route('/api/profile/order-info', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def get_order_info(self, **kwargs):
        """
        Everything a checkout page needs about one order and its current payment.

        Input JSON (one of the references is required):
        {
            "user_profile_id": 456,
            "order_code": "TEST_ABC123",
            "refresh": false
        }

        `order_code` is the code the customer sees, which is the gateway
        transaction id or, when there is none, the payment reference.
        `transaction_code` is accepted as an alias for it.

        `refresh` asks the payment provider for the live status before answering,
        which is slower but authoritative.
        """
        try:
            user_profile_id = kwargs.get('user_profile_id')
            order_code = kwargs.get('order_code') or kwargs.get('transaction_code')
            refresh = bool(kwargs.get('refresh'))

            Payment = request.env['profile.payment'].sudo()
            payment = Payment.browse()

            user_profile, error = self._find_order(user_profile_id, order_code)
            if error:
                return error

            if order_code:
                # Report the transaction the caller asked about, not the latest one,
                # as long as it really belongs to this order
                payment = Payment.search(
                    ['&', ('user_profile_id', '=', user_profile.id),
                     '|', ('transaction_id', '=', order_code),
                     ('name', '=', order_code)], limit=1)

            # Without an explicit transaction code, report the payment that is
            # actually in play: the latest one that was not cancelled
            if not payment:
                live_payments = user_profile.payment_ids.filtered(
                    lambda p: p.state != 'cancelled')
                payment = (live_payments or user_profile.payment_ids).sorted('id')[-1:]

            if payment and refresh and payment.state != 'confirmed':
                try:
                    payment.action_check_payment_status()
                except Exception:
                    # A provider hiccup must not break the whole response
                    _logger.exception(
                        "order-info: could not refresh payment %s", payment.transaction_id)

            isd_tx = payment.isd_transaction_id
            if payment and not isd_tx and payment.transaction_id:
                isd_tx = request.env['isd_payment.transaction'].sudo().search(
                    [('transaction_id', '=', payment.transaction_id)], limit=1)

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            partner = user_profile.partner_id
            state_labels = dict(user_profile._fields['state'].selection)
            payment_labels = dict(user_profile._fields['payment_status'].selection)

            order_data = {
                'id': user_profile.id,
                'name': user_profile.name or '',
                'state': user_profile.state,
                'state_label': state_labels.get(user_profile.state, ''),
                'payment_status': user_profile.payment_status,
                'payment_status_label': payment_labels.get(user_profile.payment_status, ''),
                'total_cost': user_profile.total_cost,
                'paid_amount': user_profile.paid_amount,
                'remaining_amount': user_profile.remaining_amount,
                'progress_percentage': user_profile.progress_percentage,
                'address': user_profile.address or '',
                'created_at': fields.Datetime.to_string(user_profile.create_date) or '',
                'start_date': fields.Date.to_string(user_profile.start_date) or '',
                'customer': {
                    'name': partner.name or '',
                    'email': partner.email or '',
                    'phone': partner.phone or '',
                },
                'package': {
                    'id': user_profile.profile_id.id,
                    'name': user_profile.profile_id.name or '',
                },
                'services': [{
                    'id': step.id,
                    'name': step.name or '',
                    'cost': step.cost,
                    'state': step.state,
                    'is_selected': step.is_selected,
                } for step in user_profile.user_step_ids],
            }

            transaction_data = None
            if payment:
                method = payment.payment_method_id
                transaction_data = {
                    'transaction_id': payment.transaction_id or '',
                    'payment_state': payment.state,
                    'amount': payment.amount,
                    'status': isd_tx.status if isd_tx else '',
                    'is_expired': bool(isd_tx.is_expired) if isd_tx else False,
                    'expired_at': fields.Datetime.to_string(isd_tx.expired_at) if isd_tx else '',
                    'confirmed_at': fields.Datetime.to_string(isd_tx.confirmed_at) if isd_tx else '',
                    'qr_url': (isd_tx.qr_url or '') if isd_tx else '',
                    # PayPal and VNPay send the customer to their own page instead
                    'payment_url': ((isd_tx.paypal_redirect_url or isd_tx.vnpay_redirect_url or '')
                                    if isd_tx else ''),
                    'payment_method': {
                        'id': method.id,
                        'name': method.name or '',
                        'type': method.payment_provider or '',
                        'environment': (method.environment or '') if 'environment' in method._fields else '',
                        'image_url': f"{base_url}/web/image/isd_payment.method/{method.id}/image" if method.image else '',
                    } if method else None,
                }

            # What the caller should do next, so the page does not have to guess
            tx_status = transaction_data['status'] if transaction_data else ''
            if user_profile.payment_status == 'paid' or tx_status == 'confirmed' \
                    or (payment and payment.state == 'confirmed'):
                next_action = 'done'
            elif not payment:
                next_action = 'checkout'
            elif tx_status in ('cancelled', 'failed', 'expired') or transaction_data['is_expired']:
                next_action = 'recheckout'
            else:
                next_action = 'wait'

            return {
                'success': True,
                'next_action': next_action,
                'order': order_data,
                'transaction': transaction_data,
            }

        except Exception as e:
            _logger.exception("Error getting order info via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }

    @http.route('/api/profile/check-payment', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def check_payment_status(self, **kwargs):
        """
        Check payment status for profile package

        Input JSON:
        {
            "user_profile_id": 456,
            "transaction_code": "TEST_ABC123"
        }

        Output JSON:
        {
            "success": true,
            "status": "confirmed",  // pending, confirmed, expired
            "message": "Payment confirmed successfully"
        }
        """
        try:
            # Get input parameters
            user_profile_id = kwargs.get('user_profile_id')
            transaction_code = kwargs.get('transaction_code')

            # Validate input
            if not user_profile_id:
                return {
                    'success': False,
                    'error': 'User Profile ID is required',
                    'error_code': 'MISSING_USER_PROFILE_ID'
                }

            if not transaction_code:
                return {
                    'success': False,
                    'error': 'Transaction code is required',
                    'error_code': 'MISSING_TRANSACTION_CODE'
                }

            # Find user profile
            user_profile = request.env['user.profile'].sudo().browse(user_profile_id)
            if not user_profile.exists():
                return {
                    'success': False,
                    'error': 'User profile not found',
                    'error_code': 'USER_PROFILE_NOT_FOUND'
                }

            # Find payment by user_profile_id and transaction_code
            payment = request.env['profile.payment'].sudo().search([
                ('user_profile_id', '=', user_profile_id),
                ('transaction_id', '=', transaction_code)
            ], limit=1)

            if not payment:
                return {
                    'success': False,
                    'error': 'Payment not found with given transaction code',
                    'error_code': 'PAYMENT_NOT_FOUND'
                }

            # Check payment status via isd_payment
            result = payment.action_check_payment_status()

            return {
                'success': True,
                'status': result.get('status'),
                'message': result.get('message')
            }

        except Exception as e:
            _logger.exception("Error checking payment status via external API")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }
