# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Profile Management
    user_profile_ids = fields.One2many('user.profile', 'user_id', string='Assigned Profiles')
    profile_count = fields.Integer(string='Profile Count', compute='_compute_profile_count')
    
    # User Type for Profile Management
    is_profile_student = fields.Boolean(string='Is Student', default=False)
    is_profile_manager = fields.Boolean(string='Is Manager', default=False)
    
    # Student Information
    student_id = fields.Char(string='Student ID')
    phone_number = fields.Char(string='Phone Number')
    address = fields.Text(string='Address')
    emergency_contact = fields.Char(string='Emergency Contact')
    
    @api.depends('user_profile_ids')
    def _compute_profile_count(self):
        for user in self:
            user.profile_count = len(user.user_profile_ids)
    
    def action_view_profiles(self):
        """View user's profiles"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Profiles',
            'res_model': 'user.profile',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id},
        }
    
    def action_assign_profile(self):
        """Assign a profile to user (for managers)"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Profile',
            'res_model': 'user.profile',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.id},
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically assign profile management groups to new users"""
        users = super().create(vals_list)
        
        # Get the student only group (for students who should see Student menu)
        student_only_group = self.env.ref('isd_profile_management.group_profile_student_only', raise_if_not_found=False)
        manager_group = self.env.ref('isd_profile_management.group_profile_manager', raise_if_not_found=False)
        
        for user in users:
            # Don't assign to admin or system users
            if user.login not in ['admin', '__system__']:
                # Check if user already has manager group (from data.xml or manual assignment)
                if manager_group and manager_group.id in user.groups_id.ids:
                    # User is a manager - set manager flag, don't assign student_only group
                    
                    user.is_profile_manager = True
                elif student_only_group:
                    # User is a regular student - assign student_only group
                    user.groups_id = [(4, student_only_group.id)]
                    user.is_profile_student = True
        
        return users