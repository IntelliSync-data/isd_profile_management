import secrets

from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ISD Payment Integration
    pm_payment_method_ids = fields.Many2many(
        'isd_payment.method',
        string='Default Payment Methods',
        help='Used only by a package that names no payment methods of its own. '
             'Each package decides how it can be paid, on its own form'
    )

    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_payment_method_ids', default=''
        )
        ids = [int(i) for i in param.split(',') if i.strip().isdigit()]
        existing = self.env['isd_payment.method'].sudo().browse(ids).exists().ids
        res['pm_payment_method_ids'] = [(6, 0, existing)]

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        res['pm_payment_webhook_url'] = (
            '%s/api/profile/payment-webhook' % base_url.rstrip('/') if base_url else '')
        return res

    def set_values(self):
        super().set_values()
        ids = self.pm_payment_method_ids.ids
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_profile_management.pm_payment_method_ids',
            ','.join(str(i) for i in ids)
        )

    # Currency Configuration
    pm_currency = fields.Selection(
        [('vnd', 'VND (đ)'), ('usd', 'USD ($)')],
        string='Currency',
        config_parameter='isd_profile_management.pm_currency',
        default='vnd',
    )
    pm_exchange_rate = fields.Float(
        string='Exchange Rate (1 USD = ? VND)',
        config_parameter='isd_profile_management.pm_exchange_rate',
        default=25000.0,
        help='Exchange rate used to convert between USD and VND when payment provider currency differs from package currency',
    )

    # Email Template Configuration
    pm_email_order_template_id = fields.Many2one(
        'marketing.template',
        string='Order Confirmation Email Template',
        domain=[('template_type', '=', 'email')],
        config_parameter='isd_profile_management.pm_email_order_template_id',
        help='Email template sent when a new order (package purchase) is created'
    )

    pm_email_payment_template_id = fields.Many2one(
        'marketing.template',
        string='Payment Confirmation Email Template',
        domain=[('template_type', '=', 'email')],
        config_parameter='isd_profile_management.pm_email_payment_template_id',
        help='Email template sent when payment is confirmed'
    )

    pm_send_assignment_emails = fields.Boolean(
        string='Send Assignment Emails to End Users',
        config_parameter='isd_profile_management.pm_send_assignment_emails',
        default=False,
        help='If unchecked, assignment and activity emails will only be sent to internal users/managers, not to end users'
    )

    # Invoicing
    pm_enable_invoiced_stage = fields.Boolean(
        string='Enable Invoiced Stage',
        config_parameter='isd_profile_management.pm_enable_invoiced_stage',
        default=False,
        help='Adds the Invoiced stage after Completed, plus the Mark Invoiced button on orders'
    )

    # Customer Order Page
    pm_order_link = fields.Char(
        string='Customer Order Page Link',
        config_parameter='isd_profile_management.pm_order_link',
        help='Public page where a customer opens their own order, for example '
             'https://bloompod.vn/order.html. The order code is appended automatically '
             'and the link is shown under the QR code at checkout'
    )

    # Incoming notification, for when isd_payment runs on another system
    pm_payment_webhook_secret = fields.Char(
        string='Payment Webhook Secret',
        config_parameter='isd_profile_management.pm_payment_webhook_secret',
        help='Shared with the payment system, which signs every call with it. '
             'Calls without a matching signature are refused'
    )
    pm_payment_webhook_url = fields.Char(
        string='Payment Webhook URL', readonly=True,
        help='Paste this into Notify URL on the payment method, over in ISD Payment'
    )

    def action_generate_payment_webhook_secret(self):
        """Written straight to the parameter: the settings form is transient, and
        a secret the user cannot copy before saving is useless."""
        self.ensure_one()
        secret = secrets.token_urlsafe(32)
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_profile_management.pm_payment_webhook_secret', secret)
        self.pm_payment_webhook_secret = secret
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Secret generated and saved. Copy it into ISD Payment.'),
                'type': 'success',
                'sticky': False,
            },
        }
