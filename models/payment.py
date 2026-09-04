# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProfilePayment(models.Model):
    _name = 'profile.payment'
    _description = 'Profile Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    def _message_auto_subscribe_notify(self, partner_ids, template):
        """Suppress automatic 'You have been assigned' email notifications"""
        return

    name = fields.Char(string='Payment Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    transaction_id = fields.Char(
        string='Transaction ID', required=False, copy=False, readonly=True)

    # ISD Payment Integration
    isd_transaction_id = fields.Many2one(
        'isd_payment.transaction',
        string='ISD Payment Transaction',
        readonly=True,
        help='Link to ISD Payment transaction'
    )
    qr_url = fields.Char(
        string='QR Code URL',
        related='isd_transaction_id.qr_url',
        readonly=True,
        help='QR code URL for payment'
    )

    # User and Profile
    user_id = fields.Many2one('res.users', string='User', required=True, tracking=True)
    user_profile_id = fields.Many2one('user.profile', string='User Profile', ondelete='cascade', help="Profile created after payment confirmation")
    step_selection_id = fields.Many2one('step.selection', string='Original Selection', help="Original step selection that created this payment")
    profile_id = fields.Many2one('profile.management', string='Profile', related='user_profile_id.profile_id', store=True)
    
    # Payment Details
    amount = fields.Float(string='Amount', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    payment_date = fields.Datetime(string='Payment Date', default=fields.Datetime.now, tracking=True)
    
    # Bank Information
    bank_name = fields.Char(string='Bank Name')
    bank_account = fields.Char(string='Bank Account Number')
    reference_number = fields.Char(string='Reference Number', tracking=True)
    
    # Receipt
    receipt_attachment_ids = fields.Many2many(
        'ir.attachment', 
        'payment_receipt_rel',
        'payment_id', 
        'attachment_id',
        string='Receipt Attachments'
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    # Steps
    step_ids = fields.Many2many('user.step', string='Steps to Pay', domain="[('user_profile_id', '=', user_profile_id)]")
    
    # Confirmation
    confirmed_by = fields.Many2one('res.users', string='Confirmed By', readonly=True)
    confirmed_date = fields.Datetime(string='Confirmed Date', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    
    metadata = fields.Json(string='Metadata', help="Additional metadata for the payment")

    payment_method_id = fields.Many2one(
        'isd_payment.method',
        string='Payment Method',
        help='Payment method used for this payment'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('profile.payment') or _('New')
        return super(ProfilePayment, self).create(vals_list)
    
    @api.constrains('amount')
    def _check_amount(self):
        """Validate amount is positive"""
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("Payment amount must be positive."))
    
    @api.onchange('user_profile_id')
    def _onchange_user_profile_id(self):
        """Update user_id when user_profile_id changes"""
        if self.user_profile_id:
            self.user_id = self.user_profile_id.user_id
    
    def action_submit_for_approval(self):
        """Submit payment for approval"""
        if not self.receipt_attachment_ids:
            raise ValidationError(_("Please upload a payment receipt before submitting."))
        
        self.write({'state': 'pending'})
        self.message_post(body=_("Payment submitted for approval"))
        
        # Notify managers
        self._notify_managers()
    
    def action_confirm(self):
        """Confirm payment and update profile status"""
        self.write({
            'state': 'confirmed',
            'confirmed_by': self.env.user.id,
            'confirmed_date': fields.Datetime.now(),
        })
        
        # Update user profile payment_status based on total paid vs total cost
        if self.user_profile_id:
            profile = self.user_profile_id
            confirmed_payments = self.env['profile.payment'].search([
                ('user_profile_id', '=', profile.id),
                ('state', '=', 'confirmed'),
            ])
            total_paid = sum(confirmed_payments.mapped('amount'))
            total_cost = profile.total_cost

            if total_cost > 0 and total_paid >= total_cost:
                profile.write({'payment_status': 'paid'})
            elif total_paid > 0:
                profile.write({'payment_status': 'half_paid'})
        
        self.message_post(body=_("Payment confirmed by %s") % self.env.user.name)

        # Send payment confirmation email to user
        self._send_payment_confirmation_email()

        # Notify user (only if enabled in settings)
        self._notify_user_confirmation()
    
    def action_reject(self):
        """Reject payment"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Payment'),
            'res_model': 'payment.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payment_id': self.id},
        }
    
    def action_cancel(self):
        """Cancel payment"""
        self.write({'state': 'cancelled'})
        self.message_post(body=_("Payment cancelled"))
    
    def _notify_managers(self):
        """Notify managers about new payment submission"""
        managers = self.env['res.users'].search([('groups_id', 'in', self.env.ref('isd_profile_management.group_profile_manager').id)])
        
        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=manager.id,
                summary=_('New Payment Confirmation Required'),
                note=_('Payment of %s submitted by %s needs confirmation.') % (self.amount, self.user_id.name)
            )
    
    def _notify_user_confirmation(self):
        """Notify user about payment confirmation"""
        # Check if we should send assignment emails to end users
        send_assignment_emails = self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_send_assignment_emails', 'False'
        ) == 'True'

        if send_assignment_emails:
            # Create a notification activity for the user
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary=_('Payment Confirmed'),
                note=_('Your payment of %s has been confirmed.') % self.amount
            )

    def _send_payment_confirmation_email(self):
        """Send payment confirmation email using configured marketing template"""
        self.ensure_one()

        # Get email template from config
        template_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_email_payment_template_id', 0
        ))

        if not template_id:
            _logger.warning("No payment confirmation email template configured")
            return

        template = self.env['marketing.template'].browse(template_id)
        if not template.exists():
            _logger.warning("Configured payment confirmation email template not found")
            return

        # Build flat variables from payment data
        variables = {
            'payment_name': self.name or '',
            'user_name': self.user_id.name or '',
            'user_email': self.user_id.email or '',
            'amount': f"{self.amount:,.0f} VND",
            'transaction_id': self.transaction_id or '',
            'qr_url': self.qr_url or '',
            'state': self.state or '',
            'payment_date': fields.Datetime.to_string(fields.Datetime.now()),
            'package_name': self.user_profile_id.profile_id.name if self.user_profile_id else '',
            'profile_name': self.user_profile_id.name if self.user_profile_id else '',
        }

        try:
            template.send_email_via_api(self.user_id.email, variables)
            _logger.info(f"Payment confirmation email sent to {self.user_id.email} for payment {self.name}")
        except Exception as e:
            _logger.error(f"Failed to send payment confirmation email: {str(e)}")

    # ==========================================
    # ISD Payment Integration Methods
    # ==========================================

    def action_create_isd_payment(self):
        """Create payment transaction via ISD Payment module.

        Reads the first active payment method from pm_payment_method_ids config param,
        then delegates to action_create_isd_payment_with_method.
        """
        self.ensure_one()

        # Get payment method IDs from config
        param = self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_payment_method_ids', default=''
        )
        ids = [int(i) for i in param.split(',') if i.strip().isdigit()]

        if not ids:
            raise ValidationError(_("Please configure Payment Methods in Settings first."))

        payment_method = self.env['isd_payment.method'].browse(ids[0])
        if not payment_method.exists():
            raise ValidationError(_("Configured Payment Method not found."))

        return self.action_create_isd_payment_with_method(payment_method)

    def action_create_isd_payment_with_method(self, payment_method):
        """Create payment transaction via ISD Payment module using a specific method record.

        Args:
            payment_method: isd_payment.method record

        Returns:
            dict with transaction_id, qr_url, amount
        """
        self.ensure_one()

        # Generate transaction ID using the method's prefix
        transaction_id = self.env['isd_payment.transaction'].generate_transaction_id(
            payment_method.prefix
        )

        # Get request info
        request_origin = self.env.context.get('request_origin', '')
        request_ip = self.env.context.get('request_ip', '')

        # Create ISD Payment transaction
        isd_transaction = self.env['isd_payment.transaction'].create({
            'payment_method_id': payment_method.id,
            'transaction_id': transaction_id,
            'amount': self.amount,
            'description': f"Profile Payment {self.name} - User: {self.user_id.name}",
            'qr_url': payment_method.generate_qr_url(transaction_id, self.amount),
            'bank_account': payment_method.provider_account_id,
            'bank_code': payment_method.sepay_acc_bank,
            'status': 'pending',
            'request_origin': request_origin,
            'request_ip': request_ip,
            'branch': self.user_profile_id.profile_id.name if self.user_profile_id else '',
        })

        # Link to profile payment
        self.write({
            'isd_transaction_id': isd_transaction.id,
            'transaction_id': transaction_id,
            'payment_method_id': payment_method.id,
            'state': 'pending'
        })

        self.message_post(body=_("Payment QR code generated. Transaction ID: %s") % transaction_id)

        return {
            'transaction_id': transaction_id,
            'qr_url': isd_transaction.qr_url,
            'amount': self.amount,
        }

    def action_check_payment_status(self):
        """Check payment status by directly querying isd_payment transaction and provider."""
        self.ensure_one()

        if not self.payment_method_id:
            raise ValidationError(_("No payment method linked to this payment."))

        # Check fast path: already confirmed locally
        if self.state == 'confirmed':
            return {
                'status': 'confirmed',
                'message': _('Payment already confirmed'),
            }

        # Get the isd_payment transaction
        isd_tx = self.isd_transaction_id
        if not isd_tx:
            # Try to find by transaction_id
            isd_tx = self.env['isd_payment.transaction'].sudo().search([
                ('transaction_id', '=', self.transaction_id),
                ('payment_method_id', '=', self.payment_method_id.id),
            ], limit=1)

        if not isd_tx:
            return {
                'status': 'processing',
                'message': _('Transaction not found in payment system'),
            }

        # Already confirmed in isd_payment
        if isd_tx.status == 'confirmed':
            if self.state != 'confirmed':
                self.action_confirm()
            return {
                'status': 'confirmed',
                'message': _('Payment confirmed successfully'),
            }

        # Check if expired
        if isd_tx.is_expired:
            isd_tx.mark_as_expired()
            return {
                'status': 'expired',
                'message': _('Payment has expired'),
            }

        # Mark as processing
        isd_tx.mark_as_processing()

        payment_method = self.payment_method_id
        transaction_id = isd_tx.transaction_id
        amount = int(self.amount)

        # Check with payment provider directly
        from odoo.addons.isd_payment.controllers.main import IsdPaymentController
        controller = IsdPaymentController()

        if payment_method.payment_provider == 'sepay':
            result = controller._check_sepay_transaction(
                payment_method, transaction_id, amount, prefix=payment_method.prefix
            )
        elif payment_method.payment_provider == 'vtcpay':
            result = controller._check_vtcpay_transaction(
                payment_method, transaction_id, amount
            )
        elif payment_method.payment_provider == 'paypal':
            paypal_order_id = isd_tx.paypal_order_id or transaction_id
            result = controller._check_paypal_transaction(payment_method, paypal_order_id)
        elif payment_method.payment_provider == 'acbpay':
            # ACB uses webhooks, just check DB status
            return {
                'status': 'processing',
                'message': _('Waiting for payment confirmation from ACB'),
            }
        else:
            result = controller._check_sepay_transaction(
                payment_method, transaction_id, amount, prefix=payment_method.prefix
            )

        if result.get('found'):
            isd_tx.mark_as_confirmed(result.get('data'))
            if self.state != 'confirmed':
                self.action_confirm()
            return {
                'status': 'confirmed',
                'message': _('Payment confirmed successfully'),
            }
        else:
            return {
                'status': 'processing',
                'message': result.get('message', _('Payment not yet confirmed')),
            }

    def _convert_payment_amount(self, provider):
        """Convert amount based on package currency and payment provider.

        Currency is the currency of the package price (from settings).
        - USD + PayPal → no conversion
        - USD + SePay/QR → convert USD to VND (amount * exchange_rate)
        - VND + PayPal → convert VND to USD (amount / exchange_rate)
        - VND + SePay/QR → no conversion

        Returns:
            dict with 'charge_amount' (amount to charge provider),
                       'amount_usd' (USD amount or 0),
                       'amount_vnd' (VND amount or 0)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        currency = ICP.get_param('isd_profile_management.pm_currency', 'vnd')
        exchange_rate = float(ICP.get_param('isd_profile_management.pm_exchange_rate', '25000'))

        if exchange_rate <= 0:
            exchange_rate = 25000.0

        is_paypal = provider == 'paypal'

        if currency == 'usd' and is_paypal:
            # Package in USD, PayPal accepts USD → no conversion
            return {'charge_amount': self.amount, 'amount_usd': self.amount, 'amount_vnd': 0}
        elif currency == 'usd' and not is_paypal:
            # Package in USD, SePay needs VND → multiply by rate
            amount_vnd = round(self.amount * exchange_rate)
            return {'charge_amount': amount_vnd, 'amount_usd': self.amount, 'amount_vnd': amount_vnd}
        elif currency == 'vnd' and is_paypal:
            # Package in VND, PayPal needs USD → divide by rate
            amount_usd = round(self.amount / exchange_rate, 2)
            return {'charge_amount': amount_usd, 'amount_usd': amount_usd, 'amount_vnd': self.amount}
        else:
            # VND + SePay → no conversion
            return {'charge_amount': self.amount, 'amount_usd': 0, 'amount_vnd': self.amount}

    def action_create_isd_payment_external(self, payment_method):
        """Create payment transaction via ISD Payment module for external API

        Args:
            payment_method: isd_payment.method record

        Returns:
            dict with transaction_id, qr_url/redirect_url, amount
        """
        self.ensure_one()

        provider = payment_method.payment_provider
        request_origin = self.env.context.get('request_origin', 'External API')
        request_ip = self.env.context.get('request_ip', '')

        converted = self._convert_payment_amount(provider)
        charge_amount = converted['charge_amount']

        if provider == 'paypal':
            # PayPal: create order via PayPal API (charge_amount is already USD)
            from odoo.addons.isd_payment.controllers.main import IsdPaymentController
            controller = IsdPaymentController()
            paypal_result = controller._create_paypal_payment(
                payment_method, charge_amount, already_converted=True
            )

            if not paypal_result.get('found'):
                raise ValidationError(paypal_result.get('message', 'PayPal error'))

            order_id = paypal_result['order_id']
            isd_transaction = self.env['isd_payment.transaction'].create({
                'payment_method_id': payment_method.id,
                'transaction_id': order_id,
                'amount': self.amount,
                'amount_usd': converted['amount_usd'],
                'description': f"External Profile Payment {self.name} - User: {self.user_id.name}",
                'paypal_order_id': order_id,
                'paypal_redirect_url': paypal_result.get('redirect_url'),
                'status': 'pending',
                'request_origin': request_origin,
                'request_ip': request_ip,
                'branch': self.user_profile_id.profile_id.name if self.user_profile_id else '',
            })

            self.write({
                'isd_transaction_id': isd_transaction.id,
                'transaction_id': order_id,
                'payment_method_id': payment_method.id,
                'state': 'pending'
            })

            self.message_post(body=_("PayPal payment created. Order ID: %s") % order_id)

            return {
                'transaction_id': order_id,
                'redirect_url': paypal_result.get('redirect_url'),
                'amount': self.amount,
                'amount_usd': converted['amount_usd'],
            }

        else:
            # SePay / VTCPay / ACBPay: generate QR URL (charge_amount is VND)
            transaction_id = self.env['isd_payment.transaction'].generate_transaction_id(
                payment_method.prefix
            )

            isd_transaction = self.env['isd_payment.transaction'].create({
                'payment_method_id': payment_method.id,
                'transaction_id': transaction_id,
                'amount': charge_amount,
                'description': f"External Profile Payment {self.name} - User: {self.user_id.name}",
                'qr_url': payment_method.generate_qr_url(transaction_id, charge_amount),
                'bank_account': payment_method.provider_account_id,
                'bank_code': payment_method.sepay_acc_bank,
                'status': 'pending',
                'request_origin': request_origin,
                'request_ip': request_ip,
                'branch': self.user_profile_id.profile_id.name if self.user_profile_id else '',
            })

            self.write({
                'isd_transaction_id': isd_transaction.id,
                'transaction_id': transaction_id,
                'payment_method_id': payment_method.id,
                'state': 'pending'
            })

            self.message_post(body=_("External payment QR code generated. Transaction ID: %s") % transaction_id)

            return {
                'transaction_id': transaction_id,
                'qr_url': isd_transaction.qr_url,
                'amount': self.amount,
                'amount_vnd': converted['amount_vnd'],
            }