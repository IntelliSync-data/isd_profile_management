# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IsdPaymentTransaction(models.Model):
    _inherit = 'isd_payment.transaction'

    def _on_confirmed(self):
        """Carry a confirmed transaction through to the order it paid for.

        Until now only a poll from the waiting page, or someone pressing Mark as
        Paid, moved the order. A customer who closed the page left it saying Not
        Yet Paid even though the gateway had confirmed the money.
        """
        res = super()._on_confirmed()

        Payment = self.env['profile.payment'].sudo()
        for transaction in self:
            payments = Payment.search([
                '|', ('isd_transaction_id', '=', transaction.id),
                ('transaction_id', '=', transaction.transaction_id),
            ])
            for payment in payments.filtered(lambda p: p.state != 'confirmed'):
                if not payment.isd_transaction_id:
                    # Created in another request, so the link was never written
                    payment.isd_transaction_id = transaction.id
                if payment.state == 'cancelled':
                    payment.message_post(body=
                        "Money was received on this cancelled payment: "
                        "an old QR code or payment link was used.")
                # Sets the order to Paid or Half Paid from the amounts.
                # isd_skip_cash_confirm stops the order, once paid, from also
                # confirming other payments still waiting on it: only this one
                # actually received money.
                payment.with_context(isd_skip_cash_confirm=True).action_confirm()
                _logger.info(
                    "Order %s confirmed from transaction %s",
                    payment.user_profile_id.name, transaction.transaction_id)

        return res

    def _webhook_payload(self, event='transaction.confirmed'):
        """Add the order this transaction belongs to, so the receiver does not
        have to look it up."""
        payload = super()._webhook_payload(event)

        payment = self.env['profile.payment'].sudo().search([
            '|', ('isd_transaction_id', '=', self.id),
            ('transaction_id', '=', self.transaction_id),
        ], limit=1)
        order = payment.user_profile_id
        if order:
            payload['order'] = {
                'order_code': order.order_code or '',
                'user_profile_id': order.id,
                'payment_status': order.payment_status,
                'total_cost': order.total_cost,
                'paid_amount': order.paid_amount,
                'remaining_amount': order.remaining_amount,
            }
        return payload
