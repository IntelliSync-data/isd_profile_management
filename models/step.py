# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProfileStep(models.Model):
    _name = 'profile.step'
    _description = 'Profile Step'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Step Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Profile
    profile_id = fields.Many2one('profile.management', string='Profile', required=True, ondelete='cascade')
    
    # Cost and Details
    cost = fields.Float(string='Cost', required=True, tracking=True)
    cost_vnd = fields.Char(string='Cost VND', compute='_compute_cost_vnd', store=True)
    duration_days = fields.Integer(string='Duration (Days)', help="Estimated duration in days")
    instructions = fields.Html(string='Instructions', help="Detailed instructions for this step")
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string='Status', default='draft', tracking=True)
    
    # result
    result = fields.Text(string='Result', help="Result or outcome of this step", default="", required=False)
    
    # Requirements
    is_mandatory = fields.Boolean(string='Mandatory', default=True, help="Is this step mandatory for the profile?")
    prerequisite_step_ids = fields.Many2many(
        'profile.step', 
        'step_prerequisite_rel', 
        'step_id', 
        'prerequisite_id',
        string='Prerequisites',
        help="Steps that must be completed before this step"
    )
    
    # User Steps
    user_step_ids = fields.One2many('user.step', 'step_id', string='User Steps')
    
    @api.constrains('prerequisite_step_ids')
    def _check_prerequisite_recursion(self):
        """Check for circular dependencies in prerequisites"""
        for step in self:
            if step in step.prerequisite_step_ids:
                raise ValidationError(_("A step cannot be a prerequisite of itself."))
            
            # Check for circular dependencies
            def check_circular(current_step, visited=None):
                if visited is None:
                    visited = set()
                if current_step.id in visited:
                    return True
                visited.add(current_step.id)
                for prereq in current_step.prerequisite_step_ids:
                    if check_circular(prereq, visited.copy()):
                        return True
                return False
            
            if check_circular(step):
                raise ValidationError(_("Circular dependency detected in prerequisites."))
    
    @api.constrains('cost')
    def _check_cost(self):
        """Validate cost is not negative"""
        for step in self:
            if step.cost < 0:
                raise ValidationError(_("Cost cannot be negative."))
    
    def action_activate(self):
        """Activate the step"""
        self.write({'state': 'active'})
        self.message_post(body=_("Step activated"))
    
    def action_deactivate(self):
        """Deactivate the step"""
        self.write({'state': 'inactive'})
        self.message_post(body=_("Step deactivated"))
    
    def action_view_user_steps(self):
        """View user steps for this step"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('User Steps'),
            'res_model': 'user.step',
            'view_mode': 'list,form',
            'domain': [('step_id', '=', self.id)],
            'context': {'default_step_id': self.id},
        }
    
    @api.depends('cost')
    def _compute_cost_vnd(self):
        for record in self:
            record.cost_vnd = self._format_vnd_currency(record.cost)
    
    def _format_vnd_currency(self, amount):
        """Format Vietnamese currency according to requirements:
        1000 vnd = 1Kđ
        1000000 = 1Mđ
        1300000 = 1.300Kđ
        1299000 = 1299Kđ
        """
        if not amount:
            return '0đ'
        
        amount = int(amount)
        
        if amount >= 1000000:
            # Millions
            millions = amount // 1000000
            remainder = amount % 1000000
            
            if remainder == 0:
                return f'{millions}Mđ'
            elif remainder % 1000 == 0:
                # Show as X.XXXKđ format
                thousands = remainder // 1000
                if thousands < 100:
                    return f'{millions}.{thousands:03d}Kđ'
                else:
                    return f'{millions}.{thousands}Kđ'
            else:
                # Show full amount with thousands separator
                total_thousands = amount // 1000
                if total_thousands >= 1000:
                    return f'{total_thousands:,}Kđ'.replace(',', '.')
                else:
                    return f'{total_thousands}Kđ'
        elif amount >= 1000:
            # Thousands
            thousands = amount // 1000
            remainder = amount % 1000
            
            if remainder == 0:
                return f'{thousands}Kđ'
            else:
                # Less than 1000K, show full amount
                return f'{amount}đ'
        else:
            # Less than 1000
            return f'{amount}đ'