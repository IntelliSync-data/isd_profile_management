# -*- coding: utf-8 -*-
from odoo import models, fields


class ProfileInvoiceWizard(models.TransientModel):
    _name = 'profile.invoice.wizard'
    _description = 'Mark Order Invoiced'

    user_profile_id = fields.Many2one(
        'user.profile', string='Order', required=True, readonly=True)
    invoice_number = fields.Char(string='Invoice Number')
    invoice_date = fields.Date(string='Invoice Date', default=fields.Date.context_today)

    def action_confirm(self):
        """Both invoice fields are optional, the stage change is what matters"""
        self.ensure_one()
        return self.user_profile_id.action_mark_invoiced(
            invoice_number=self.invoice_number,
            invoice_date=self.invoice_date,
        )
