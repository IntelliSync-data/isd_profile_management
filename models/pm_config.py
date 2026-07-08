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
