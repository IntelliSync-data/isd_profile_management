# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PaymentMethodSelectWizard(models.TransientModel):
    _name = 'payment.method.select.wizard'
    _description = 'Select Payment Method'

    user_profile_id = fields.Many2one('user.profile', required=True)
    # Not required: the wizard is created before a method is picked, and a required
    # field would break that create with a database constraint error
    payment_method_id = fields.Many2one(
        'isd_payment.method',
        string='Payment Method',
        default=lambda self: self._default_payment_method_id(),
    )
    available_method_ids = fields.Many2many(
        'isd_payment.method',
        compute='_compute_available_method_ids',
    )

    @api.model
    def _get_available_methods(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_payment_method_ids', default=''
        )
        ids = [int(i) for i in param.split(',') if i.strip().isdigit()]
        return self.env['isd_payment.method'].sudo().browse(ids).filtered(
            lambda m: m.exists() and m.active and m.is_configured
        )

    @api.model
    def _default_payment_method_id(self):
        return self._get_available_methods()[:1].id or False

    @api.depends('user_profile_id')
    def _compute_available_method_ids(self):
        methods = self._get_available_methods()
        for rec in self:
            rec.available_method_ids = methods

    def action_confirm(self):
        self.ensure_one()
        if not self.payment_method_id:
            raise ValidationError(_("Please select a payment method."))
        return self.user_profile_id.action_checkout_payment(self.payment_method_id.id)
