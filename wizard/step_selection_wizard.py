# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StepSelectionWizard(models.TransientModel):
    _name = 'step.selection.wizard'
    _description = 'Step Selection Wizard'

    profile_id = fields.Many2one('profile.management', string='Profile', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', default=lambda self: self.env.user.partner_id)
    selected_step_ids = fields.Many2many(
        'profile.step',
        string='Select Steps',
        domain="[('state', '=', 'active')]"
    )

    def action_confirm(self):
        """Create step selection and close wizard"""
        existing = self.env['step.selection'].search([
            ('partner_id', '=', self.partner_id.id),
            ('profile_id', '=', self.profile_id.id),
            ('state', '=', 'draft')
        ], limit=1)

        if existing:
            existing.unlink()

        selection = self.env['step.selection'].create({
            'partner_id': self.partner_id.id,
            'profile_id': self.profile_id.id,
            'selected_step_ids': [(6, 0, self.selected_step_ids.ids)],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'step.selection',
            'res_id': selection.id,
            'view_mode': 'form',
            'target': 'current',
        }
