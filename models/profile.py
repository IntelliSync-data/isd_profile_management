# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProfileManagement(models.Model):
    _name = 'profile.management'
    _description = 'Profile Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Profile Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string='Status', default='draft', tracking=True)
    
    # Steps
    step_ids = fields.Many2many('profile.step', 'profile_management_step_rel', 'profile_id', 'step_id', string='Steps')
    total_steps = fields.Integer(string='Total Steps', compute='_compute_step_counts', store=True)
    package_cost = fields.Float(string='Package Cost', default=0.0, tracking=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    total_cost_vnd = fields.Char(string='Total Cost VND', compute='_compute_total_cost_vnd', store=True)
    
    # Options
    is_advanced = fields.Boolean(string='Advanced', default=False, help="Enable advanced step flow (Start → Complete → Approve)")
    is_auto_complete = fields.Boolean(string='Auto Complete', default=False, help="Automatically mark profile as completed when all selected steps are approved")

    # Users
    user_profile_ids = fields.One2many('user.profile', 'profile_id', string='User Profiles')
    assigned_user_count = fields.Integer(string='Assigned Users', compute='_compute_user_counts', store=True)
    
    # Dates
    create_date = fields.Datetime(string='Created Date', readonly=True)
    create_uid = fields.Many2one('res.users', string='Created By', readonly=True)
    
    @api.depends('step_ids')
    def _compute_step_counts(self):
        for record in self:
            record.total_steps = len(record.step_ids)
    
    @api.depends('step_ids.cost', 'package_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.step_ids.mapped('cost')) + record.package_cost
    
    @api.depends('total_cost')
    def _compute_total_cost_vnd(self):
        for record in self:
            record.total_cost_vnd = self._format_vnd_currency(record.total_cost)
    
    @api.depends('user_profile_ids')
    def _compute_user_counts(self):
        for record in self:
            record.assigned_user_count = len(record.user_profile_ids)
    
    def action_activate(self):
        """Activate the profile"""
        self.write({'state': 'active'})
        self.message_post(body=_("Profile activated"))
    
    def action_deactivate(self):
        """Deactivate the profile"""
        self.write({'state': 'inactive'})
        self.message_post(body=_("Profile deactivated"))
    
    def action_view_users(self):
        """View users assigned to this profile"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assigned Users'),
            'res_model': 'user.profile',
            'view_mode': 'list,form',
            'domain': [('profile_id', '=', self.id)],
            'context': {'default_profile_id': self.id},
        }
    
    def action_view_steps(self):
        """View steps for this profile"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Profile Steps'),
            'res_model': 'profile.step',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.step_ids.ids)],
        }
    
    # Manager Dashboard Actions
    def action_create_step(self):
        """Create new step/item"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create New Service Item'),
            'res_model': 'profile.step',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_view_all_steps(self):
        """View all steps/items"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Service Items'),
            'res_model': 'profile.step',
            'view_mode': 'list,form',
        }
    
    def action_create_package(self):
        """Create new package"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create New Package'),
            'res_model': 'profile.management',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_view_packages(self):
        """View all packages"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Packages'),
            'res_model': 'profile.management',
            'view_mode': 'list,form',
        }
    
    def action_package_builder(self):
        """Package builder wizard"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Package Builder'),
                'message': _('Package builder feature coming soon! For now, use "Create New Package" to build packages.'),
                'type': 'info',
            }
        }
    
    def action_assign_package(self):
        """Assign package to student"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Package to Student'),
            'res_model': 'user.profile',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assigned_by': self.env.user.id},
        }
    
    def action_view_assignments(self):
        """View all assignments"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('All User Assignments'),
            'res_model': 'user.profile',
            'view_mode': 'list,form',
        }
    
    def action_student_progress(self):
        """View student progress"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Progress'),
            'res_model': 'user.profile',
            'view_mode': 'kanban,list',
            'domain': [('state', 'in', ['in_progress', 'paid'])],
        }
    
    def action_package_report(self):
        """Package performance report"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Package Report'),
                'message': _('Package performance reports coming soon!'),
                'type': 'info',
            }
        }
    
    def action_revenue_report(self):
        """Revenue report"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Revenue Report'),
                'message': _('Revenue reports coming soon!'),
                'type': 'info',
            }
        }
    
    def action_student_report(self):
        """Student progress report"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Student Report'),
                'message': _('Student progress reports coming soon!'),
                'type': 'info',
            }
        }

    def action_view_api_doc(self):
        """View API documentation for external integration"""
        self.ensure_one()

        # Create wizard with API documentation
        wizard = self.env['profile.api.documentation.wizard'].create({
            'package_id': self.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('API Documentation - %s') % self.name,
            'res_model': 'profile.api.documentation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

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