from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ISD Payment Integration
    pm_payment_method_ids = fields.Many2many(
        'isd_payment.method',
        string='Payment Methods',
        help='Select payment methods from ISD Payment module'
    )

    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_payment_method_ids', default=''
        )
        ids = [int(i) for i in param.split(',') if i.strip().isdigit()]
        res['pm_payment_method_ids'] = [(6, 0, ids)]
        return res

    def set_values(self):
        super().set_values()
        ids = self.pm_payment_method_ids.ids
        self.env['ir.config_parameter'].sudo().set_param(
            'isd_profile_management.pm_payment_method_ids',
            ','.join(str(i) for i in ids)
        )

    # Legacy SePay fields (deprecated - use pm_payment_method_id instead)
    pm_sepay_host = fields.Char(
        string="SEPAY Host",
        config_parameter='isd_profile_management.pm_sepay_host'
    )

    pm_sepay_qr_host = fields.Char(
        string="SEPAY QR Host",
        config_parameter='isd_profile_management.pm_sepay_qr_host'
    )
    
    pm_sepay_acc_number = fields.Char(
        string="SEPAY Account Number",
        config_parameter='isd_profile_management.pm_sepay_acc_number'
    )
    
    pm_sepay_acc_bank = fields.Char(
        string="SEPAY Account Bank",
        config_parameter='isd_profile_management.pm_sepay_acc_bank'
    )
    
    pm_sepay_api_token = fields.Char(
        string="SEPAY API Token",
        config_parameter='isd_profile_management.pm_sepay_api_token'
    )
    
    pm_sepay_prefix_transaction_id = fields.Char(
        string="SEPAY Transaction ID Prefix",
        config_parameter='isd_profile_management.pm_sepay_prefix_transaction_id'
    )
    
    pm_vtcpay_host = fields.Char(
        string="VTC Pay Host",
        config_parameter='isd_profile_management.pm_vtcpay_host'
    )
    pm_vtcpay_key_sign = fields.Char(
        string="VTC Pay Key Sign",
        config_parameter='isd_profile_management.pm_vtcpay_key_sign'
    )
    pm_vtcpay_website_id = fields.Char(
        string="VTC Pay Website ID",
        config_parameter='isd_profile_management.pm_vtcpay_website_id'
    )
    pm_vtcpay_security_code = fields.Char(
        string="VTC Pay Security Code",
        config_parameter='isd_profile_management.pm_vtcpay_security_code'
    )
    pm_vtcpay_payment_type = fields.Char(
        string="VTC Pay Payment Type",
        config_parameter='isd_profile_management.pm_vtcpay_payment_type'
    )
    pm_vtcpay_receiver_account = fields.Char(
        string="VTC Pay Receiver Account",
        config_parameter='isd_profile_management.pm_vtcpay_receiver_account'
    )
    
    pm_paypal_host = fields.Char(
        string="PayPal Host",
        config_parameter='isd_profile_management.pm_paypal_host'
    )
    pm_paypal_client_id = fields.Char(
        string="PayPal Client ID",
        config_parameter='isd_profile_management.pm_paypal_client_id'
    )
    pm_paypal_client_secret = fields.Char(
        string="PayPal Client Secret",
        config_parameter='isd_profile_management.pm_paypal_client_secret'
    )
    pm_paypal_mode = fields.Selection(
        [("sandbox", "Sandbox"), ("live", "Live")],
        string="PayPal Mode",
        config_parameter='isd_profile_management.pm_paypal_mode'
    )
    pm_paypal_usd_exchange_rate = fields.Float(
        string="PayPal USD Exchange Rate",
        config_parameter='isd_profile_management.pm_paypal_usd_exchange_rate',
        default=26_300
    )

    # Currency Configuration
    pm_currency = fields.Selection(
        [('vnd', 'VND (đ)'), ('usd', 'USD ($)')],
        string='Currency',
        config_parameter='isd_profile_management.pm_currency',
        default='vnd',
    )

    # Email Template Configuration
    pm_email_order_template_id = fields.Many2one(
        'marketing.template',
        string='Order Confirmation Email Template',
        domain=[('template_type', '=', 'email'), ('module_reference', '=', 'isd_profile_management')],
        config_parameter='isd_profile_management.pm_email_order_template_id',
        help='Email template sent when a new order (package purchase) is created'
    )

    pm_email_payment_template_id = fields.Many2one(
        'marketing.template',
        string='Payment Confirmation Email Template',
        domain=[('template_type', '=', 'email'), ('module_reference', '=', 'isd_profile_management')],
        config_parameter='isd_profile_management.pm_email_payment_template_id',
        help='Email template sent when payment is confirmed'
    )

    pm_send_assignment_emails = fields.Boolean(
        string='Send Assignment Emails to End Users',
        config_parameter='isd_profile_management.pm_send_assignment_emails',
        default=False,
        help='If unchecked, assignment and activity emails will only be sent to internal users/managers, not to end users'
    )
    