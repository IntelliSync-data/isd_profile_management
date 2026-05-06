# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PaymentRejectionWizard(models.TransientModel):
    _name = 'payment.rejection.wizard'
    _description = 'Payment Rejection Wizard'

    payment_id = fields.Many2one('profile.payment', string='Payment', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True, 
                                   help="Please provide a clear reason for rejecting this payment")
    
    def action_reject_payment(self):
        """Reject the payment with reason"""
        if not self.rejection_reason:
            raise ValidationError(_("Please provide a reason for rejection."))
        
        # Update payment with rejection
        self.payment_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason,
        })
        
        # Post message to payment
        self.payment_id.message_post(
            body=_("Payment rejected by %s. Reason: %s") % (self.env.user.name, self.rejection_reason)
        )
        
        # Notify user via activity
        self.payment_id.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.payment_id.user_id.id,
            summary=_('Payment Rejected'),
            note=_('Your payment of %s has been rejected. Reason: %s') % (
                self.payment_id.amount, self.rejection_reason
            )
        )
        
        return {'type': 'ir.actions.act_window_close'}