# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PrintLabelWizard(models.TransientModel):
    _name = 'print.label.wizard'
    _description = 'Print Label Wizard'

    user_step_id = fields.Many2one('user.step', string='Step', required=True)
    tracking_number = fields.Char(string='Tracking Number', required=True)

    step_name = fields.Char(related='user_step_id.step_id.name', readonly=True)
    print_width = fields.Integer(related='user_step_id.step_id.print_width', readonly=True)
    print_height = fields.Integer(related='user_step_id.step_id.print_height', readonly=True)
    print_code_type = fields.Selection(related='user_step_id.step_id.print_code_type', readonly=True)

    def action_print(self):
        """Save tracking number and return print data for JS to render"""
        self.ensure_one()
        if not self.tracking_number:
            raise ValidationError(_("Please enter a tracking number."))

        step = self.user_step_id
        step.write({'tracking_number': self.tracking_number})

        print_data = step._get_print_data()
        template_html = step.step_id.print_template or ''

        return {
            'type': 'ir.actions.client',
            'tag': 'isd_print_label',
            'params': {
                'width': step.step_id.print_width,
                'height': step.step_id.print_height,
                'code_type': step.step_id.print_code_type,
                'tracking_number': self.tracking_number,
                'template': template_html,
                'data': print_data,
            },
        }
