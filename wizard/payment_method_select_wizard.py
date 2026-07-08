# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PaymentMethodSelectWizard(models.TransientModel):
    _name = 'payment.method.select.wizard'
    _description = 'Select Payment Method'

    user_profile_id = fields.Many2one('user.profile', required=True)
    payment_method_id = fields.Many2one(
        'isd_payment.method',
        string='Payment Method',
        required=True,
    )
    available_method_ids = fields.Many2many(
        'isd_payment.method',
        compute='_compute_available_method_ids',
    )

    @api.depends('user_profile_id')
    def _compute_available_method_ids(self):
        for rec in self:
            param = self.env['ir.config_parameter'].sudo().get_param(
                'isd_profile_management.pm_payment_method_ids', default=''
            )
            ids = [int(i) for i in param.split(',') if i.strip().isdigit()]
            methods = self.env['isd_payment.method'].browse(ids).filtered(
                lambda m: m.exists() and m.active and m.is_configured
            )
            rec.available_method_ids = methods

    def action_confirm(self):
        self.ensure_one()
        return self.user_profile_id.action_checkout_payment(self.payment_method_id.id)
