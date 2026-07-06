# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StepSelection(models.Model):
    _name = 'step.selection'
    _description = 'User Step Selection'
    _rec_name = 'profile_id'
    
    # User and Profile
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    profile_id = fields.Many2one('profile.management', string='Profile', required=True)
    
    # Selection Details
    name = fields.Char(string='Selection Name', compute='_compute_name', store=True)
    available_step_ids = fields.Many2many(
        'profile.step',
        string='Available Steps',
        compute='_compute_available_steps'
    )
    selected_step_ids = fields.Many2many(
        'profile.step', 
        'step_selection_step_rel', 
        'selection_id', 
        'step_id',
        string='Selected Steps'
    )
    
    # Calculated Fields
    total_cost = fields.Float(string='Total Cost', compute='_compute_totals', store=True)
    total_cost_vnd = fields.Char(string='Total Cost VND', compute='_compute_total_cost_vnd', store=True)
    total_steps = fields.Integer(string='Total Steps Selected', compute='_compute_totals', store=True)
    
    # Profile Management
    created_profile_id = fields.Many2one('user.profile', string='Created Profile', readonly=True, help="Profile created after payment confirmation")
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('quoted', 'Quoted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft')
    
    # Dates
    create_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)
    confirm_date = fields.Datetime(string='Confirmed Date')

    # Notes
    notes = fields.Text(string='Notes', help='Additional notes for this profile assignment')
    
    @api.depends('user_id', 'profile_id')
    def _compute_name(self):
        for record in self:
            if record.user_id and record.profile_id:
                record.name = f"{record.user_id.name} - {record.profile_id.name}"
            else:
                record.name = "New Selection"
    
    @api.depends('selected_step_ids.cost')
    def _compute_totals(self):
        for record in self:
            record.total_steps = len(record.selected_step_ids)
            record.total_cost = sum(record.selected_step_ids.mapped('cost'))
    
    @api.depends('selected_step_ids.cost')
    def _compute_total_cost_vnd(self):
        for record in self:
            record.total_cost_vnd = self._format_vnd_currency(record.total_cost)
    
    @api.depends('profile_id')
    def _compute_available_steps(self):
        """Compute available steps for selection"""
        for record in self:
            if record.profile_id:
                record.available_step_ids = self.env['profile.step'].search([
                    ('state', '=', 'active')
                ])
            else:
                record.available_step_ids = False
    
    @api.model
    def default_get(self, fields_list):
        """Set default values and ensure proper loading"""
        defaults = super().default_get(fields_list)
        if 'profile_id' in self.env.context:
            profile_id = self.env.context.get('profile_id')
            if profile_id:
                defaults['profile_id'] = profile_id
                # Auto-select all available steps by default
                available_steps = self.env['profile.step'].search([
                    ('state', '=', 'active')
                ])
                defaults['selected_step_ids'] = [(6, 0, available_steps.ids)]
        return defaults
    
    @api.onchange('profile_id')
    def _onchange_profile_id(self):
        """Update domain when profile changes and auto-select all steps"""
        if self.profile_id:
            # Auto-select all available steps
            available_steps = self.env['profile.step'].search([
                ('state', '=', 'active')
            ])
            self.selected_step_ids = [(6, 0, available_steps.ids)]

            return {
                'domain': {
                    'selected_step_ids': [
                        ('state', '=', 'active')
                    ]
                }
            }
    
    def _format_vnd_currency(self, amount):
        """Format Vietnamese currency according to requirements"""
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
    
    def action_confirm_selection(self):
        """Confirm the step selection and create user profile"""
        if not self.selected_step_ids:
            raise ValidationError(_("Please select at least one step before confirming."))
        
        self.write({
            'state': 'confirmed',
            'confirm_date': fields.Datetime.now(),
        })
        
        # Create user profile immediately after confirmation
        user_profile = self._create_user_profile_from_selection()
        
        # Redirect directly to the profile detail page
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Profile'),
            'res_model': 'user.profile',
            'res_id': user_profile.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _create_user_profile_from_selection(self):
        """Create user profile from step selection"""
        # Check if user already has a profile for this package
        existing_profile = self.env['user.profile'].search([
            ('user_id', '=', self.user_id.id),
            ('profile_id', '=', self.profile_id.id)
        ], limit=1)
        
        if existing_profile:
            # Update existing profile with new steps
            user_profile = existing_profile
            # Delete existing user steps to replace with selected ones
            existing_profile.user_step_ids.unlink()
        else:
            # Create new user profile without triggering automatic step creation
            user_profile = self.env['user.profile'].with_context(skip_create_steps=True).create({
                'user_id': self.user_id.id,
                'profile_id': self.profile_id.id,
                'state': 'new',
                'assigned_date': fields.Datetime.now(),
                'assigned_by': self.user_id.id,
            })
        
        # Create user step instances ONLY for selected steps
        for step in self.selected_step_ids:
            self.env['user.step'].create({
                'user_id': self.user_id.id,
                'step_id': step.id,
                'user_profile_id': user_profile.id,
                'state': 'not_started',
                'payment_status': 'not_paid',
                'is_selected': True,
                'cost': step.cost,
            })
        
        # Link the created profile back to this selection
        self.created_profile_id = user_profile.id
        
        # Log profile creation
        user_profile.message_post(
            body=_("Profile created from step selection. %d steps selected.") % len(self.selected_step_ids)
        )
        
        return user_profile
    
    def action_get_quote(self):
        """Generate an order for selected steps"""
        if self.state != 'confirmed':
            raise ValidationError(_("Please confirm the selection first before getting an order."))
        
        if not self.selected_step_ids:
            raise ValidationError(_("Please select at least one step to get an order."))
        
        self.write({'state': 'quoted'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Order Generated'),
                'message': _('Your order has been generated! Total: %s for %s steps.') % (self.total_cost_vnd, self.total_steps),
                'type': 'success',
            }
        }
    
    def action_create_payment(self):
        """Create payment for selected steps"""
        if not self.selected_step_ids:
            raise ValidationError(_("No steps selected for payment."))
        
        payment = self.env['profile.payment'].create({
            'user_id': self.user_id.id,
            'amount': self.total_cost,
            'step_ids': [(6, 0, self.selected_step_ids.ids)],
            'step_selection_id': self.id,
            'notes': f"Payment for {self.profile_id.name} - {self.total_steps} steps selected",
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Make Payment'),
            'res_model': 'profile.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ProfileManagement(models.Model):
    _inherit = 'profile.management'
    
    # Add step selection tracking
    selection_ids = fields.One2many('step.selection', 'profile_id', string='User Selections')
    selection_count = fields.Integer(string='Selections Count', compute='_compute_selection_count')
    
    @api.depends('selection_ids')
    def _compute_selection_count(self):
        for record in self:
            record.selection_count = len(record.selection_ids)
    
    def action_select_steps(self):
        """Open step selection form for current user"""
        # Check if user already has a draft selection
        existing_selection = self.env['step.selection'].search([
            ('user_id', '=', self.env.user.id),
            ('profile_id', '=', self.id),
            ('state', '=', 'draft')
        ], limit=1)
        
        if existing_selection:
            selection_id = existing_selection.id
        else:
            # Create new selection
            selection = self.env['step.selection'].create({
                'user_id': self.env.user.id,
                'profile_id': self.id,
            })
            selection_id = selection.id
        
        # Return action to redirect to URL like window.location.href
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/web#id={selection_id}&model=step.selection&view_type=form"
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }
    
    def action_view_selections(self):
        """View all user selections for this profile"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('User Selections'),
            'res_model': 'step.selection',
            'view_mode': 'list,form',
            'domain': [('profile_id', '=', self.id)],
            'context': {'default_profile_id': self.id},
        }