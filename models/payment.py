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
        
        # Update user steps to paid status
        if self.step_ids:
            self.step_ids.write({'payment_status': 'paid'})
        
        # Update user profile status to paid if all steps are paid
        if self.user_profile_id:
            unpaid_steps = self.user_profile_id.user_step_ids.filtered(lambda s: s.is_selected and s.payment_status != 'paid')
            if not unpaid_steps:
                self.user_profile_id.write({'state': 'paid'})
        
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
        """Send payment confirmation email using configured template"""
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

        # Prepare email data
        email_data = {
            'object': {
                'name': self.name,
                'user_id': {
                    'name': self.user_id.name,
                    'email': self.user_id.email,
                },
                'amount': f"{self.amount:,.0f} VND",
                'transaction_id': self.transaction_id or '',
                'qr_url': self.qr_url or '',
                'state': self.state,
                'payment_date': fields.Datetime.to_string(fields.Datetime.now()),
            },
            'company': {
                'name': self.env.company.name,
                'email': self.env.company.email or 'info@company.com',
            },
            'user': {
                'name': self.env.user.name,
            }
        }

        # Render template
        try:
            email_body = template.render_template(email_data)
            email_subject = template.render_subject(email_data)

            # Send email
            mail_values = {
                'subject': email_subject,
                'body_html': email_body,
                'email_to': self.user_id.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }

            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()

            # Increment template usage
            template.increment_usage()

            _logger.info(f"Payment confirmation email sent to {self.user_id.email} for payment {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send payment confirmation email: {str(e)}")

    # ==========================================
    # ISD Payment Integration Methods
    # ==========================================

    def action_create_isd_payment(self):
        """Create payment transaction via ISD Payment module"""
        self.ensure_one()

        # Get payment method from config
        payment_method_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_payment_method_id', 0
        ))

        if not payment_method_id:
            raise ValidationError(_("Please configure Payment Method in Settings first."))

        payment_method = self.env['isd_payment.method'].browse(payment_method_id)
        if not payment_method.exists():
            raise ValidationError(_("Configured Payment Method not found."))

        # Generate transaction ID
        transaction_id = self.env['isd_payment.transaction'].generate_transaction_id(
            payment_method.sepay_prefix_transaction_id
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
            'bank_account': payment_method.sepay_acc_number,
            'bank_code': payment_method.sepay_acc_bank,
            'status': 'pending',
            'request_origin': request_origin,
            'request_ip': request_ip,
        })

        # Link to profile payment
        self.write({
            'isd_transaction_id': isd_transaction.id,
            'transaction_id': transaction_id,
            'state': 'pending'
        })

        self.message_post(body=_("Payment QR code generated. Transaction ID: %s") % transaction_id)

        return {
            'transaction_id': transaction_id,
            'qr_url': isd_transaction.qr_url,
            'amount': self.amount,
        }

    def action_check_payment_status(self):
        """Check payment status from ISD Payment transaction"""
        self.ensure_one()

        if not self.isd_transaction_id:
            raise ValidationError(_("No ISD Payment transaction linked."))

        # Check if already confirmed
        if self.isd_transaction_id.status == 'confirmed':
            # Auto-confirm profile payment
            if self.state != 'confirmed':
                self.action_confirm()
            return {
                'status': 'confirmed',
                'message': _('Payment already confirmed')
            }

        # Check if expired
        if self.isd_transaction_id.is_expired:
            self.isd_transaction_id.mark_as_expired()
            return {
                'status': 'expired',
                'message': _('Payment has expired')
            }

        # Call check payment from ISD Payment
        payment_method = self.isd_transaction_id.payment_method_id

        # Import controller helper
        from odoo.addons.isd_payment.controllers.main import IsdPaymentController
        controller = IsdPaymentController()

        result = controller._check_sepay_transaction(
            payment_method,
            self.isd_transaction_id.transaction_id,
            int(self.amount),
            prefix=payment_method.sepay_prefix_transaction_id
        )

        if result.get('found'):
            # Mark ISD transaction as confirmed
            self.isd_transaction_id.mark_as_confirmed(result.get('data'))

            # Auto-confirm profile payment
            if self.state != 'confirmed':
                self.action_confirm()

            return {
                'status': 'confirmed',
                'message': _('Payment confirmed successfully')
            }
        else:
            return {
                'status': 'processing',
                'message': result.get('message', _('Payment not found yet'))
            }

    def action_create_isd_payment_external(self, payment_method):
        """Create payment transaction via ISD Payment module for external API

        Args:
            payment_method: isd_payment.method record

        Returns:
            dict with transaction_id, qr_url, amount
        """
        self.ensure_one()

        # Generate transaction ID
        transaction_id = self.env['isd_payment.transaction'].generate_transaction_id(
            payment_method.sepay_prefix_transaction_id
        )

        # Get request info from context
        request_origin = self.env.context.get('request_origin', 'External API')
        request_ip = self.env.context.get('request_ip', '')

        # Create ISD Payment transaction
        isd_transaction = self.env['isd_payment.transaction'].create({
            'payment_method_id': payment_method.id,
            'transaction_id': transaction_id,
            'amount': self.amount,
            'description': f"External Profile Payment {self.name} - User: {self.user_id.name}",
            'qr_url': payment_method.generate_qr_url(transaction_id, self.amount),
            'bank_account': payment_method.sepay_acc_number,
            'bank_code': payment_method.sepay_acc_bank,
            'status': 'pending',
            'request_origin': request_origin,
            'request_ip': request_ip,
        })

        # Link to profile payment
        self.write({
            'isd_transaction_id': isd_transaction.id,
            'transaction_id': transaction_id,
            'state': 'pending'
        })

        self.message_post(body=_("External payment QR code generated. Transaction ID: %s") % transaction_id)

        return {
            'transaction_id': transaction_id,
            'qr_url': isd_transaction.qr_url,
            'amount': self.amount,
        }