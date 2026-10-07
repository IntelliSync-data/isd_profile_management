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
    def _package_environment(self, package):
        """Real money only for a Live package, test gateways for a Demo one.

        Driven by the package type, not by its status: a Live package parked as
        Inactive is still a live package.
        """
        return 'live' if package and package.package_type == 'live' else 'test'

    @api.model
    def _get_available_methods(self, package=None):
        """How an order of this package can be paid.

        The package decides, because one package may take cash at the counter
        while another only takes a card. A package naming none accepts none.
        """
        methods = package.payment_method_ids.sudo() if package else self.env['isd_payment.method']
        methods = methods.filtered(lambda m: m.exists() and m.active and m.is_configured)

        # guarded: isd_payment may still be running a version without the flag
        if package and 'environment' in self.env['isd_payment.method']._fields:
            environment = self._package_environment(package)
            methods = methods.filtered(lambda m: m.environment == environment)
        return methods

    @api.model
    def _check_method_for_package(self, package, method=None):
        """Refuse a package with no method of its environment, or a foreign method"""
        methods = self._get_available_methods(package)
        if not methods:
            environment = self._package_environment(package)
            raise ValidationError(_(
                "This package accepts no %s payment method. "
                "Add one under Payment Methods on the package."
            ) % (_("Live") if environment == 'live' else _("Test")))

        if method and method not in methods:
            raise ValidationError(_(
                "Payment method %s cannot be used for this package."
            ) % (method.name or ''))
        return methods

    @api.model
    def _default_payment_method_id(self):
        profile_id = self.env.context.get('default_user_profile_id')
        package = self.env['user.profile'].browse(profile_id).profile_id if profile_id else None
        return self._get_available_methods(package)[:1].id or False

    @api.depends('user_profile_id')
    def _compute_available_method_ids(self):
        for rec in self:
            rec.available_method_ids = self._get_available_methods(
                rec.user_profile_id.profile_id)

    def action_confirm(self):
        self.ensure_one()
        if not self.payment_method_id:
            raise ValidationError(_("Please select a payment method."))
        self._check_method_for_package(
            self.user_profile_id.profile_id, self.payment_method_id)
        return self.user_profile_id.action_checkout_payment(self.payment_method_id.id)
