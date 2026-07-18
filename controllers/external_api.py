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

    @http.route('/api/profile/create', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def create_profile_package(self, **kwargs):
        """
        Create profile package for external user

        Input JSON:
        {
            "package_id": 123,
            "email": "user@example.com",
            "notes": "Customer info: Name, Phone, Address",
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
            payment_method_id = kwargs.get('payment_method_id')

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

            # Find or create user by email
            user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if not user:
                # Create new user
                user = request.env['res.users'].sudo().create({
                    'name': email.split('@')[0],  # Use email prefix as name
                    'login': email,
                    'email': email,
                    'active': True,
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])]
                })

            # Check if user already has a profile for this package
            existing_profile = request.env['user.profile'].sudo().search([
                ('user_id', '=', user.id),
                ('profile_id', '=', package.id)
            ], limit=1)

            if existing_profile:
                user_profile = existing_profile
                # Delete existing steps to replace with new ones
                existing_profile.user_step_ids.unlink()
            else:
                # Create new user profile with all steps from package
                user_profile = request.env['user.profile'].sudo().with_context(skip_create_steps=True).create({
                    'user_id': user.id,
                    'profile_id': package.id,
                    'state': 'new',
                    'assigned_date': fields.Datetime.now(),
                    'assigned_by': user.id,
                    'notes': notes,
                })

            # Get all active steps from package
            active_steps = package.step_ids.filtered(lambda s: s.state == 'active')

            # Validate package has steps
            if not active_steps:
                return {
                    'success': False,
                    'error': 'Package has no active steps configured',
                    'error_code': 'NO_STEPS'
                }

            # Create user step instances for all steps
            user_step_ids = []
            for step in active_steps:
                user_step = request.env['user.step'].sudo().create({
                    'user_id': user.id,
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

            # Calculate total cost
            total_amount = sum(active_steps.mapped('cost'))

            # Validate total amount
            if total_amount <= 0:
                return {
                    'success': False,
                    'error': 'Package has no cost or all steps are free',
                    'error_code': 'INVALID_AMOUNT'
                }

            # Create profile payment (link to user_step records that were just created)
            profile_payment = request.env['profile.payment'].sudo().create({
                'user_profile_id': user_profile.id,
                'user_id': user.id,
                'amount': total_amount,
                'step_ids': [(6, 0, user_step_ids)],
                'state': 'draft',
            })

            # Generate QR code via isd_payment integration
            payment_response = profile_payment.with_context(
                payment_method_id=payment_method_id
            ).action_create_isd_payment_external(payment_method)

            # Update user profile state
            user_profile.write({'state': 'not_yet_paid'})

            # Send order confirmation email
            user_profile._send_order_confirmation_email()

            # Log creation (but don't send to end user unless enabled)
            user_profile.message_post(
                body=_("Profile created via external API. Email: %s, Notes: %s") % (email, notes),
                message_type='comment',  # Internal note, not sent to user
                subtype_xmlid='mail.mt_note'  # Internal note subtype
            )

            return {
                'success': True,
                'user_profile_id': user_profile.id,
                'transaction_id': payment_response.get('transaction_id'),
                'qr_url': payment_response.get('qr_url'),
                'amount': total_amount,
            }

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
