# -*- coding: utf-8 -*-
import base64
import io
import logging
import requests as http_requests
from PIL import Image
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    _name = 'user.profile'
    _description = 'User Profile Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)

    # User and Profile
    user_id = fields.Many2one(
        'res.users', string='User', required=True, tracking=True)
    profile_id = fields.Many2one(
        'profile.management', string='Profile', required=True, tracking=True)

    # Status
    state = fields.Selection([
        ('new', 'New'),
        ('not_yet_paid', 'Not Yet Paid'),
        ('paid', 'Paid'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True)

    # Progress
    progress_percentage = fields.Float(
        string='Progress %', compute='_compute_progress', store=True)

    # Dates
    start_date = fields.Date(string='Start Date', tracking=True)
    expected_completion_date = fields.Date(string='Expected Completion Date')
    actual_completion_date = fields.Date(
        string='Actual Completion Date', readonly=True)

    # Steps
    user_step_ids = fields.One2many(
        'user.step', 'user_profile_id', string='User Steps')
    selected_step_ids = fields.Many2many(
        'user.step',
        string='Selected Steps',
        compute='_compute_selected_steps',
        help="Steps selected by the user"
    )

    # Costs
    total_cost = fields.Float(
        string='Total Cost', compute='_compute_costs', store=True)
    paid_amount = fields.Float(
        string='Paid Amount', compute='_compute_costs', store=True)
    remaining_amount = fields.Float(
        string='Remaining Amount', compute='_compute_costs', store=True)

    # Manager Assignment
    assigned_by = fields.Many2one(
        'res.users', string='Assigned By', default=lambda self: self.env.user)
    assigned_date = fields.Datetime(
        string='Assigned Date', default=fields.Datetime.now)

    result = fields.Text(
        string='Result', help="Result or outcome of this step", default="", required=False)

    # Notes
    notes = fields.Text(string='Notes', help='Additional notes for this profile assignment')

    @api.depends('user_id', 'profile_id')
    def _compute_name(self):
        for record in self:
            if record.user_id and record.profile_id:
                record.name = f"{record.user_id.name} - {record.profile_id.name}"
            else:
                record.name = "New Assignment"

    @api.depends('user_step_ids.state')
    def _compute_progress(self):
        for record in self:
            if record.user_step_ids:
                completed_steps = record.user_step_ids.filtered(
                    lambda s: s.state == 'completed')
                record.progress_percentage = (
                    len(completed_steps) / len(record.user_step_ids)) * 100
            else:
                record.progress_percentage = 0.0

    @api.depends('user_step_ids.is_selected', 'user_step_ids.cost', 'user_step_ids.payment_status')
    def _compute_costs(self):
        for record in self:
            selected_steps = record.user_step_ids.filtered('is_selected')
            record.total_cost = sum(selected_steps.mapped('cost'))

            paid_steps = selected_steps.filtered(
                lambda s: s.payment_status == 'paid')
            record.paid_amount = sum(paid_steps.mapped('cost'))

            record.remaining_amount = record.total_cost - record.paid_amount

    @api.depends('user_step_ids.is_selected')
    def _compute_selected_steps(self):
        for record in self:
            record.selected_step_ids = record.user_step_ids.filtered(
                'is_selected')

    @api.model_create_multi
    def create(self, vals_list):
        records = super(UserProfile, self).create(vals_list)
        # Only create steps automatically if not explicitly skipped
        if not self.env.context.get('skip_create_steps', False):
            for record in records:
                record._create_user_steps()
        return records

    def _create_user_steps(self):
        """Create user steps from profile steps"""
        for step in self.profile_id.step_ids.filtered(lambda s: s.state == 'active'):
            self.env['user.step'].create({
                'user_profile_id': self.id,
                'step_id': step.id,
                'user_id': self.user_id.id,
            })

    def action_start_profile(self):
        """Start working on the profile"""
        self.write({
            'state': 'in_progress',
            'start_date': fields.Date.today(),
        })
        self.message_post(body=_("Profile started"))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_show_result_popup(self):
        mandatory_steps = self.user_step_ids.filtered(
            lambda s: s.step_id.is_mandatory and s.is_selected)
        incomplete_steps = mandatory_steps.filtered(
            lambda s: s.state != 'completed')

        if incomplete_steps:
            raise ValidationError(
                _("Cannot complete profile. The following mandatory steps are not completed: %s") %
                ', '.join(incomplete_steps.mapped('step_id.name'))
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Đánh giá kết quả',
            'res_model': 'user.profile',
            'view_mode': 'form',
            'views': [(self.env.ref('isd_profile_management.view_profile_result_popup').id, 'form')],
            'res_id': self.id,
            'target': 'new',  # 'new' opens it as a modal popup
            'context': {
                'result': self.result,  # optional: pre-fill fields
                'form_view_initial_mode': 'edit',  # open in edit mode
            }
        }

    def action_complete_profile(self):
        """Mark profile as completed"""
        # Check if all mandatory steps are completed
        mandatory_steps = self.user_step_ids.filtered(
            lambda s: s.step_id.is_mandatory and s.is_selected)
        incomplete_steps = mandatory_steps.filtered(
            lambda s: s.state != 'completed')

        if incomplete_steps:
            raise ValidationError(
                _("Cannot complete profile. The following mandatory steps are not completed: %s") %
                ', '.join(incomplete_steps.mapped('step_id.name'))
            )

        self.write({
            'state': 'completed',
            'actual_completion_date': fields.Date.today(),
        })
        self.message_post(body=_("Profile completed"))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_cancel_profile(self):
        """Cancel the profile"""
        self.write({'state': 'cancelled'})
        self.user_step_ids.write({'state': 'cancelled'})
        self.message_post(body=_("Profile cancelled"))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_view_payments(self):
        """View payments for this profile"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'profile.payment',
            'view_mode': 'list,form',
            'domain': [('user_profile_id', '=', self.id)],
            'context': {'default_user_profile_id': self.id, 'default_user_id': self.user_id.id},
        }

    def action_get_order(self):
        """Get order for the profile - changes status to Not Yet Paid"""
        if self.state != 'new':
            raise ValidationError(
                _("Order can only be requested for new profiles."))

        self.write({'state': 'not_yet_paid'})
        self.message_post(body=_("Order requested by %s") % self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_mark_paid(self):
        """Manager marks the profile as paid"""
        if self.state not in ['new', 'not_yet_paid']:
            raise ValidationError(
                _("Can only mark profiles as paid when they are 'New' or 'Not Yet Paid'."))

        self.write({'state': 'paid'})
        self.message_post(
            body=_("Payment confirmed by manager %s") % self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_set_pending(self):
        """Manager sets profile to pending status"""
        if self.state not in ['paid', 'in_progress']:
            raise ValidationError(
                _("Can only set status to pending from paid or in_progress states."))

        self.write({'state': 'pending'})
        self.message_post(
            body=_("Status set to pending by manager %s") % self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_resume_progress(self):
        """Manager resumes profile from pending to in_progress"""
        if self.state != 'pending':
            raise ValidationError(
                _("Can only resume progress from pending state."))

        self.write({'state': 'in_progress'})
        self.message_post(
            body=_("Progress resumed by manager %s") % self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_get_quote(self):
        """Generate an order for the profile"""
        if self.state not in ['confirmed', 'in_progress']:
            raise ValidationError(
                _("Please confirm the profile first before getting an order."))

        selected_steps = self.user_step_ids.filtered('is_selected')

        if not selected_steps:
            raise ValidationError(_("No steps selected for order."))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Order Generated'),
                'message': _('Total: %s for %s steps. Use "Make Payment" to proceed.') % (self.total_cost, len(selected_steps)),
                'type': 'success',
            }
        }

    def action_checkout_payment(self, payment_method_id):
        """Unified checkout action that calls isd_payment REST API to create a payment.

        Args:
            payment_method_id (int): ID of the isd_payment.method record to use.

        Returns:
            Odoo action dict — either act_url (redirect) or act_window (QR wizard).
        """
        if self.state != 'not_yet_paid':
            raise ValidationError(
                _("Payment can only be made when profile is 'Not Yet Paid'."))

        action_id = self.env.ref(
            'isd_profile_management.action_my_profiles').id

        selected_steps = self.user_step_ids.filtered(
            lambda s: s.is_selected and s.payment_status in ['pending', 'not_paid'])

        if not selected_steps:
            raise ValidationError(_("No steps selected for payment."))

        total_amount = sum(selected_steps.mapped('cost'))

        payment_method = self.env['isd_payment.method'].browse(payment_method_id)
        if not payment_method.exists():
            raise ValidationError(_("Payment method not found."))

        # Call isd_payment REST API to create the payment
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        try:
            response = http_requests.post(
                f"{base_url}/api/payment/{payment_method_id}/create",
                json={
                    "amount": total_amount,
                    "description": f"Profile Payment - {self.name}",
                },
                timeout=30,
            )
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            raise ValidationError(
                _("Could not reach payment service. Please try again later. Error: %s") % e)

        result = response.json()
        if not result.get('success'):
            raise ValidationError(result.get('error', _('Payment creation failed')))

        data = result['data']
        transaction_id = data['transaction_id']
        qr_url = data.get('qr_url')
        redirect_url = data.get('redirect_url')

        # Link to isd_payment.transaction record created by the API
        isd_tx = self.env['isd_payment.transaction'].sudo().search(
            [('transaction_id', '=', transaction_id)], limit=1)

        if qr_url:
            # QR-based flow (e.g. SePay) — create profile payment in draft state
            profile_payment = self.env['profile.payment'].create({
                'user_profile_id': self.id,
                'user_id': self.user_id.id,
                'amount': total_amount,
                'step_ids': [(6, 0, selected_steps.ids)],
                'state': 'draft',
                'transaction_id': transaction_id,
                'payment_method_id': payment_method.id,
                'isd_transaction_id': isd_tx.id if isd_tx else False,
                'metadata': {"action_id": action_id},
            })

            try:
                img_response = http_requests.get(qr_url, timeout=10)
                img_response.raise_for_status()
                img = Image.open(io.BytesIO(img_response.content))
                resized_img = img.resize((400, 400))
                buffer = io.BytesIO()
                resized_img.save(buffer, format='PNG')
                qr_image = base64.b64encode(buffer.getvalue()).decode('ascii')
            except http_requests.exceptions.RequestException as e:
                raise ValidationError(
                    _("Could not retrieve QR code. Please try again later. Error: %s") % e)

            wizard = self.env['qr.popup.wizard'].create({
                'qr_image': qr_image,
                'transaction_id': transaction_id,
            })
            return {
                'type': 'ir.actions.act_window',
                'name': 'QR Checkout',
                'res_model': 'qr.popup.wizard',
                'view_mode': 'form',
                'view_id': self.env.ref('isd_profile_management.view_qr_code_checkout').id,
                'res_id': wizard.id,
                'target': 'new',
                'context': {'form_view_initial_mode': 'edit'},
            }

        elif redirect_url:
            # Redirect-based flow (e.g. VTCPay, PayPal)
            self.env['profile.payment'].create({
                'user_profile_id': self.id,
                'user_id': self.user_id.id,
                'amount': total_amount,
                'step_ids': [(6, 0, selected_steps.ids)],
                'state': 'pending',
                'transaction_id': transaction_id,
                'payment_method_id': payment_method.id,
                'isd_transaction_id': isd_tx.id if isd_tx else False,
                'metadata': {"action_id": action_id},
            })

            return {
                'type': 'ir.actions.act_url',
                'url': redirect_url,
                'target': 'new',
            }

        else:
            raise ValidationError(_("Payment service returned no QR or redirect URL."))

    def action_open_checkout_wizard(self):
        """Open wizard to select payment method and proceed to checkout."""
        self.ensure_one()
        if self.state != 'not_yet_paid':
            raise ValidationError(_("Payment can only be made when profile is 'Not Yet Paid'."))
        wizard = self.env['payment.method.select.wizard'].create({
            'user_profile_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Payment Method'),
            'res_model': 'payment.method.select.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_make_payment(self):
        """Create a new payment"""
        selected_steps = self.user_step_ids.filtered(
            lambda s: s.is_selected and s.payment_status in ['pending', 'not_paid'])

        if not selected_steps:
            raise ValidationError(_("No steps selected for payment."))

        total_amount = sum(selected_steps.mapped('cost'))

        payment = self.env['profile.payment'].create({
            'user_profile_id': self.id,
            'user_id': self.user_id.id,
            'amount': total_amount,
            'step_ids': [(6, 0, selected_steps.ids)],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Make Payment'),
            'res_model': 'profile.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _send_order_confirmation_email(self):
        """Send order confirmation email using configured template"""
        self.ensure_one()

        # Get email template from config
        template_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'isd_profile_management.pm_email_order_template_id', 0
        ))

        if not template_id:
            _logger.warning("No order confirmation email template configured")
            return

        template = self.env['marketing.template'].browse(template_id)
        if not template.exists():
            _logger.warning("Configured order confirmation email template not found")
            return

        # Calculate total cost
        total_cost = sum(step.step_id.cost for step in self.user_step_ids if step.is_selected)

        # Prepare email data
        email_data = {
            'object': {
                'name': self.name,
                'user_id': {
                    'name': self.user_id.name,
                    'email': self.user_id.email,
                },
                'profile_id': {
                    'name': self.profile_id.name,
                },
                'total_cost': f"{total_cost:,.0f} VND",
                'state': self.state,
                'assigned_date': fields.Datetime.to_string(self.assigned_date) if self.assigned_date else '',
            },
            'company': {
                'name': self.env.company.name,
                'email': self.env.company.email or 'info@company.com',
            },
            'user': {
                'name': self.env.user.name,
            }
        }

        # Render template
        try:
            email_body = template.render_template(email_data)
            email_subject = template.render_subject(email_data)

            # Send email
            mail_values = {
                'subject': email_subject,
                'body_html': email_body,
                'email_to': self.user_id.email,
                'email_from': self.env.company.email or 'noreply@company.com',
            }

            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()

            # Increment template usage
            template.increment_usage()

            _logger.info(f"Order confirmation email sent to {self.user_id.email} for profile {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send order confirmation email: {str(e)}")


class UserStep(models.Model):
    _name = 'user.step'
    _description = 'User Step'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, step_id'

    name = fields.Char(string='Step Name', related='step_id.name', store=True)
    sequence = fields.Integer(
        string='Sequence', related='step_id.sequence', store=True)

    # Relations
    user_profile_id = fields.Many2one(
        'user.profile', string='User Profile', required=True, ondelete='cascade')
    step_id = fields.Many2one(
        'profile.step', string='Step', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True)

    # Step Details
    cost = fields.Float(string='Cost', related='step_id.cost', store=True)
    description = fields.Text(string='Description',
                              related='step_id.description')
    instructions = fields.Html(
        string='Instructions', related='step_id.instructions')
    is_mandatory = fields.Boolean(
        string='Mandatory', related='step_id.is_mandatory')

    # Selection and Status
    is_selected = fields.Boolean(
        string='Selected', default=False, tracking=True)
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('pending_approval', 'Pending Approval'),
    ], string='Status', default='not_started', tracking=True)

    # Payment
    payment_status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ], string='Payment Status', default='not_paid', tracking=True)

    # Progress
    progress_notes = fields.Text(string='Progress Notes')
    start_datetime = fields.Datetime(string='Start Time')
    deadline = fields.Date(string='Deadline')
    completion_datetime = fields.Datetime(string='Complete Time', readonly=True)

    # Computed from profile
    is_advanced = fields.Boolean(string='Advanced', related='user_profile_id.profile_id.is_advanced', store=True)

    # Manager Updates
    manager_notes = fields.Text(string='Manager Notes')
    result = fields.Text(
        string='Result', help="Result or outcome of this step", default="", required=False)
    updated_by = fields.Many2one('res.users', string='Last Updated By')

    def action_select_step(self):
        """Select this step"""
        self.write({'is_selected': True})
        self.message_post(body=_("Step selected"))

    def action_deselect_step(self):
        """Deselect this step"""
        self.write({'is_selected': False, 'state': 'not_started'})
        self.message_post(body=_("Step deselected"))

    def action_start_step(self):
        """Start working on this step"""
        if not self.is_selected:
            raise ValidationError(
                _("Cannot start a step that is not selected."))

        self.write({
            'state': 'in_progress',
            'start_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_("Step started"))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_open_popup(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả',
            'res_model': 'user.step',
            'view_mode': 'form',
            'views': [(self.env.ref('isd_profile_management.view_step_result_popup').id, 'form')],
            'res_id': self.id,
            'target': 'new',  # 'new' opens it as a modal popup
            'context': {
                'result': self.result,  # optional: pre-fill fields
                'form_view_initial_mode': 'edit',  # open in edit mode
            }
        }

    def action_show_result(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả',
            'res_model': 'user.step',
            'view_mode': 'form',
            'views': [(self.env.ref('isd_profile_management.view_step_result_popup').id, 'form')],
            'res_id': self.id,
            'target': 'new',  # 'new' opens it as a modal popup
            'context': {
                'result': self.result,  # optional: pre-fill fields
                'form_view_initial_mode': 'readonly',  # open in view mode
                'show_confirm_button': 'false',  # hide confirm button
            }
        }

    def action_complete_step(self):
        """Mark step as completed (requires manager approval) — Advanced flow only"""
        self.write({
            'state': 'pending_approval',
            'completion_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_("Step completion submitted for approval"))

        # Notify manager
        self._notify_manager_completion()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_approve_completion(self):
        """Manager approves step completion — used by both Advanced (via popup) and Simple flow (via popup)"""
        self.write({
            'state': 'completed',
            'completion_datetime': fields.Datetime.now(),
            'updated_by': self.env.user.id,
            'result': self.result,
        })
        self.message_post(
            body=_("Step completion approved by %s") % self.env.user.name)

        self._check_auto_complete_profile()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_reject_completion(self):
        """Manager rejects step completion — Advanced flow only"""
        self.write({
            'state': 'in_progress',
            'updated_by': self.env.user.id,
        })
        self.message_post(
            body=_("Step completion rejected by %s") % self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_simple_approve(self):
        """Open approve popup for Simple flow (not_started → popup note → completed)"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả',
            'res_model': 'user.step',
            'view_mode': 'form',
            'views': [(self.env.ref('isd_profile_management.view_step_result_popup').id, 'form')],
            'res_id': self.id,
            'target': 'new',
            'context': {
                'result': self.result,
                'form_view_initial_mode': 'edit',
            }
        }

    def _check_auto_complete_profile(self):
        """Auto complete user.profile if is_auto_complete is enabled and all selected steps are completed"""
        profile = self.user_profile_id
        if not profile or not profile.profile_id.is_auto_complete:
            return
        if profile.state == 'completed':
            return
        selected_steps = profile.user_step_ids.filtered('is_selected')
        if selected_steps and all(s.state == 'completed' for s in selected_steps):
            profile.write({
                'state': 'completed',
                'actual_completion_date': fields.Date.today(),
            })
            profile.message_post(body=_("Profile auto-completed: all steps approved"))

    def _notify_manager_completion(self):
        """Notify manager about step completion"""
        managers = self.env['res.users'].search([('groups_id', 'in', self.env.ref(
            'isd_profile_management.group_profile_manager').id)])

        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=manager.id,
                summary=_('Step Completion Approval Required'),
                note=_('Step "%s" completed by %s needs approval.') % (
                    self.name, self.user_id.name)
            )

# External Service Integrations and Utilities
