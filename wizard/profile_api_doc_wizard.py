# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProfileAPIDocumentationWizard(models.TransientModel):
    _name = 'profile.api.documentation.wizard'
    _description = 'Profile Package API Documentation Wizard'

    package_id = fields.Many2one('profile.management', string='Package', required=True)
    package_name = fields.Char(related='package_id.name', string='Package Name', readonly=True)
    base_url = fields.Char(string='Base URL', compute='_compute_base_url', readonly=True)

    # API Documentation fields
    api_package_info_doc = fields.Html(string='Package Info API', compute='_compute_api_documentation')
    api_create_doc = fields.Html(string='Create Package API', compute='_compute_api_documentation')
    api_check_doc = fields.Html(string='Check Payment Status API', compute='_compute_api_documentation')
    api_confirm_doc = fields.Html(string='Confirm Payment API', compute='_compute_api_documentation')

    @api.depends('package_id')
    def _compute_base_url(self):
        """Get base URL from system parameters"""
        for wizard in self:
            wizard.base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')

    @api.depends('package_id', 'base_url')
    def _compute_api_documentation(self):
        """Generate API documentation HTML"""
        for wizard in self:
            if not wizard.package_id:
                wizard.api_package_info_doc = ''
                wizard.api_create_doc = ''
                wizard.api_check_doc = ''
                wizard.api_confirm_doc = ''
                continue

            # Get payment methods for documentation
            payment_methods = self.env['isd_payment.method'].sudo().search([])
            payment_methods_list = '<br/>'.join([
                f'• ID: {pm.id} - {pm.name}' for pm in payment_methods
            ])

            # API 0: Package Info
            promo_info = f', Promotional Price: {wizard.package_id.promotional_cost}' if wizard.package_id.use_promotional_price else ''
            wizard.api_package_info_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">ℹ️ Get Package Info</h3>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/package-info
    </div>

    <h4>Headers:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
Content-Type: application/json</pre>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "package_id": {wizard.package_id.id}
    }}
}}</pre>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>package_id</strong> (required): Package ID = <code>{wizard.package_id.id}</code></li>
    </ul>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "package": {{
            "id": {wizard.package_id.id},
            "name": "{wizard.package_id.name}",
            "description": "...",
            "state": "{wizard.package_id.state}",
            "package_cost": {wizard.package_id.package_cost},
            "use_promotional_price": {'true' if wizard.package_id.use_promotional_price else 'false'},
            "promotional_cost": {wizard.package_id.promotional_cost},
            "total_cost": {wizard.package_id.total_cost},
            "total_cost_display": "{wizard.package_id.total_cost_display}",
            "services": [
                {{"id": 1, "name": "Service Name", "cost": 500000}},
                ...
            ]
        }}
    }}
}}</pre>

    <h4>Example cURL:</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/package-info' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "package_id": {wizard.package_id.id}
    }}
  }}'</pre>

    <h4 style="color: #3498db;">ℹ️ Pricing Info:</h4>
    <div style="background-color: #d1ecf1; padding: 10px; border-left: 3px solid #3498db; margin-top: 10px;">
        <strong>Package Cost:</strong> {wizard.package_id.package_cost}{promo_info}<br/>
        <strong>Total Cost:</strong> {wizard.package_id.total_cost} ({wizard.package_id.total_cost_display})<br/>
        <br/>
        If <code>use_promotional_price</code> is <code>true</code>, the <code>total_cost</code> equals the <code>promotional_cost</code> (can be 0 for free).<br/>
        Otherwise, <code>total_cost</code> = <code>package_cost</code> + sum of all service costs.
    </div>
</div>
'''

            # API 1: Create Package
            wizard.api_create_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">📦 API 1: Create Profile Package</h3>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/create
    </div>

    <h4>Headers:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
Content-Type: application/json</pre>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "package_id": {wizard.package_id.id},
        "email": "customer@example.com",
        "notes": "Nguyen Van A, 0123456789, Ho Chi Minh City",
        "payment_method_id": 1,
        "half_payment": false
    }}
}}</pre>

    <h4>Available Payment Methods:</h4>
    <div style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
        {payment_methods_list or 'No payment methods configured. Please add payment methods in ISD Payment module.'}
    </div>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>package_id</strong> (required): Package ID = <code>{wizard.package_id.id}</code></li>
        <li><strong>email</strong> (required): Customer email</li>
        <li><strong>notes</strong> (optional): Additional customer information (name, phone, address, etc.)</li>
        <li><strong>payment_method_id</strong> (required): Payment method ID from ISD Payment module</li>
        <li><strong>half_payment</strong> (optional, default: false): If <code>true</code>, only pay 50% of the total amount. Payment status will be set to <code>half_paid</code>. Call this API again to pay the remaining 50%.</li>
    </ul>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "user_profile_id": 456,
        "transaction_id": "TEST_ABC123",
        "qr_url": "https://img.vietqr.io/image/...",
        "amount": {wizard.package_id.total_cost}
    }}
}}</pre>

    <h4>Error Response:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #e74c3c;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": false,
        "error": "Error message",
        "error_code": "ERROR_CODE"
    }}
}}</pre>

    <h4>Example cURL (Full Payment):</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/create' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "package_id": {wizard.package_id.id},
      "email": "customer@example.com",
      "notes": "Customer Name, Phone, Address",
      "payment_method_id": 1
    }}
  }}'</pre>

    <h4>Example cURL (Half Payment - 50%):</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/create' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "package_id": {wizard.package_id.id},
      "email": "customer@example.com",
      "notes": "Customer Name, Phone, Address",
      "payment_method_id": 1,
      "half_payment": true
    }}
  }}'</pre>

    <h4 style="color: #3498db;">Payment Status Flow:</h4>
    <div style="background-color: #d1ecf1; padding: 10px; border-left: 3px solid #3498db; margin-top: 10px;">
        <ul style="margin: 0;">
            <li><strong>Not Yet Paid</strong> - Initial status when profile is created</li>
            <li><strong>Half Paid</strong> - After first 50% payment is confirmed (half_payment = true)</li>
            <li><strong>Paid</strong> - After full payment is confirmed (or remaining 50% is paid)</li>
            <li><strong>Returned</strong> - When payment is refunded by manager</li>
        </ul>
    </div>
</div>
'''

            # API 2: Check Payment Status
            wizard.api_check_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">🔍 API 2: Check Payment Status</h3>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/check-payment
    </div>

    <h4>Headers:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
Content-Type: application/json</pre>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "user_profile_id": 456,
        "transaction_code": "TEST_ABC123"
    }}
}}</pre>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>user_profile_id</strong> (required): User profile ID from API 1 response</li>
        <li><strong>transaction_code</strong> (required): Transaction code from API 1 response</li>
    </ul>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "status": "confirmed",
        "message": "Payment confirmed successfully"
    }}
}}</pre>

    <h4>Possible Status Values:</h4>
    <ul>
        <li><code>confirmed</code> - Payment has been verified and confirmed</li>
        <li><code>processing</code> - Payment is pending, not found in bank yet</li>
        <li><code>expired</code> - Payment transaction has expired</li>
    </ul>

    <h4>Error Response:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #e74c3c;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": false,
        "error": "Error message",
        "error_code": "ERROR_CODE"
    }}
}}</pre>

    <h4>Example cURL:</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/check-payment' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "user_profile_id": 456,
      "transaction_code": "TEST_ABC123"
    }}
  }}'</pre>

    <h4 style="color: #3498db;">ℹ️ Note:</h4>
    <div style="background-color: #d1ecf1; padding: 10px; border-left: 3px solid #3498db; margin-top: 10px;">
        This API will check the payment status with the payment gateway (SePay) automatically.
        <br/>If payment is found and confirmed, it will update the payment status accordingly:
        <ul>
            <li><code>not_yet_paid</code> → <code>half_paid</code> (if half payment was used)</li>
            <li><code>not_yet_paid</code> or <code>half_paid</code> → <code>paid</code> (if fully paid)</li>
        </ul>
    </div>
</div>
'''

            # API 3: Confirm Payment (Manual)
            wizard.api_confirm_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">✅ API 3: Confirm Payment (Manual)</h3>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/confirm-payment
    </div>

    <h4>Headers:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
Content-Type: application/json</pre>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "user_profile_id": 456,
        "transaction_code": "TEST_ABC123"
    }}
}}</pre>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>user_profile_id</strong> (required): User profile ID from API 1 response</li>
        <li><strong>transaction_code</strong> (required): Transaction code from API 1 response</li>
    </ul>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "message": "Payment confirmed successfully"
    }}
}}</pre>

    <h4>Error Response:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #e74c3c;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": false,
        "error": "Error message",
        "error_code": "ERROR_CODE"
    }}
}}</pre>

    <h4>Example cURL:</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/confirm-payment' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "user_profile_id": 456,
      "transaction_code": "TEST_ABC123"
    }}
  }}'</pre>

    <h4 style="color: #e67e22;">⚠️ Note:</h4>
    <div style="background-color: #fff3cd; padding: 10px; border-left: 3px solid #e67e22; margin-top: 10px;">
        This API only validates that the transaction_code matches the user_profile_id.
        <br/>It does NOT check with the payment gateway.
        <br/>You should verify the payment on your side before calling this API.
    </div>
</div>
'''
