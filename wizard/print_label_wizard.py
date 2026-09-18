# -*- coding: utf-8 -*-
from odoo import models, fields


class PrintLabelWizard(models.TransientModel):
    _name = 'print.label.wizard'
    _description = 'Print Label Wizard'

    user_step_id = fields.Many2one('user.step', string='Step', required=True)
    barcode_value = fields.Char(string='Barcode')
    qrcode_value = fields.Char(string='QR Code')

    step_name = fields.Char(related='user_step_id.step_id.name', readonly=True)
    print_width = fields.Integer(related='user_step_id.step_id.print_width', readonly=True)
    print_height = fields.Integer(related='user_step_id.step_id.print_height', readonly=True)
    print_barcode = fields.Boolean(related='user_step_id.step_id.print_barcode', readonly=True)
    print_qrcode = fields.Boolean(related='user_step_id.step_id.print_qrcode', readonly=True)

    def action_print(self):
        """Save code values and return print data for JS to render"""
        self.ensure_one()
        result = self.user_step_id.action_print_label(self.barcode_value, self.qrcode_value)
        return {
            'type': 'ir.actions.client',
            'tag': 'isd_print_label',
            'params': result,
        }
