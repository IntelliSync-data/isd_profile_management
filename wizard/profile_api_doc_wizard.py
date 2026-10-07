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
    api_order_doc = fields.Html(string='Order Info API', compute='_compute_api_documentation')
    api_create_payment_doc = fields.Html(string='Create Payment API', compute='_compute_api_documentation')
    api_payment_webhook_doc = fields.Html(string='Payment Webhook API', compute='_compute_api_documentation')
    api_cancel_order_doc = fields.Html(string='Cancel Order API', compute='_compute_api_documentation')

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
                wizard.api_order_doc = ''
                wizard.api_create_payment_doc = ''
                wizard.api_payment_webhook_doc = ''
                wizard.api_cancel_order_doc = ''
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

    <h4>Response Notes:</h4>
    <ul>
        <li><strong>payment_methods</strong>: the methods this package accepts, named on the package itself, narrowed to the package type — a <strong>Live</strong> package gets the <code>live</code> methods, a <strong>Demo</strong> one gets the <code>test</code> methods. Use one of these <code>id</code> values as <code>payment_method_id</code> when calling <code>/api/profile/create</code>; any other id is refused with <code>PAYMENT_METHOD_NOT_ALLOWED</code>. <code>image_url</code> is empty when the method has no logo. <code>transfer</code> carries the account details for a customer who pays by transfer rather than by scanning: <code>types</code> (<code>qr_pay</code> and/or <code>bank_transfer</code>), <code>bank_account</code>, <code>bank_name</code> and <code>bank_code</code>. It is empty for providers that have none, and comes back from API 1 and API 5 as well, beside <code>qr_url</code>. <code>notice</code> carries the wording to show for the method — <code>title</code> and <code>description</code>, set on the payment method and mostly used to explain how cash is collected. Empty when nothing was written.</li>
        <li>Send <strong>lang</strong> with any of these calls to choose the language, e.g. <code>"lang": "vi_VN"</code>. <code>"vi"</code> works too. The method name, its description and its notice come back in that language, as do the stage and payment labels. A language that is not installed is ignored and the default is used; the answer to this call says which one was applied in <code>lang</code>, and lists what can be asked for in <code>languages</code>.</li>
    </ul>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "payment_methods": [
            {{"id": 1, "name": "SePay Main", "type": "sepay", "environment": "live", "description": "Bank transfer via QR code", "image_url": "{wizard.base_url}/web/image/isd_payment.method/1/image"}},
            ...
        ],
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
        "name": "Nguyen Van A",
        "phone": "0901234567",
        "notes": "Extra information about this order",
        "address": "123 Nguyen Hue, District 1, Ho Chi Minh City",
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
        <li><strong>email</strong> (required): Customer email, used to find or create the contact</li>
        <li><strong>name</strong> (optional): Customer name. Used when creating the contact; on an existing contact it only fills a missing name. Without it the contact is named after the email.</li>
        <li><strong>phone</strong> (optional): Customer phone. Used when creating the contact; on an existing contact it only fills a missing phone.</li>
        <li><strong>notes</strong> (optional): Additional information saved on the order</li>
        <li><strong>address</strong> (optional): Delivery address, saved to the order's Address field. Shown on the order when the product has <em>Accept Address</em> enabled, or whenever an address is saved.</li>
        <li><strong>payment_method_id</strong> (optional): Payment method ID from ISD Payment module. Leave it out to create the order without paying yet: no payment is started, no gateway is called, and <code>amount</code> comes back as the full price. Pay it later with API 5.</li>
        <li><strong>metadata</strong> (optional): an object of your own, stored on the order and
            handed back by API 4 untouched. <code>metadata.gift.product_id</code> is the one key
            this module reads: the product is taken out of circulation as the order is created, and
            a second customer reaching for the same one is refused with
            <code>child_unavailable</code> instead of getting an order. Nothing releases it again;
            staff unhide it by hand if the order comes to nothing. Namespace what you put in it, so two sites using this
            field for different things never collide. Must be an object and under 8 KB; the contents
            are never inspected. It stays on the order, so a transaction expiring and a new one
            taking its place does not lose it.</li>
        <li><strong>order_code</strong> is returned by every call: a random public reference for this order. Use it, not <code>user_profile_id</code>, on a customer page — ids are sequential and can be walked to read someone else's order.</li>
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
      "name": "Nguyen Van A",
      "phone": "0901234567",
      "address": "123 Nguyen Hue, District 1, Ho Chi Minh City",
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
      "name": "Nguyen Van A",
      "phone": "0901234567",
      "address": "123 Nguyen Hue, District 1, Ho Chi Minh City",
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

            # API 4: Order Info
            wizard.api_order_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">📋 API 4: Order Info</h3>
    <p>One call that returns the order, its current transaction and what to do next.
    Use it to render an order page, to re-open a checkout page after a reload, or to
    decide whether the customer still has to pay.</p>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/order-info
    </div>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "user_profile_id": 456,
        "refresh": false
    }}
}}</pre>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>user_profile_id</strong>: order ID returned by API 1, also available in email templates
            as the <code>user_profile_id</code> variable. Required unless order_code is sent.</li>
        <li><strong>order_code</strong>: the code the customer sees — the gateway transaction id, or the
            payment reference when the gateway gave none. Same value as the <code>order_code</code> email
            variable. <code>transaction_code</code> is accepted as an alias.</li>
        <li><strong>refresh</strong> (optional, default false): ask the payment provider for the live status first.
            Slower, but authoritative. Leave it false while polling often.</li>
    </ul>
    <p>Without an order_code the answer describes the latest payment that was not cancelled.</p>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "next_action": "wait",
        "order": {{
            "id": 456,
            "name": "John Doe - {wizard.package_id.name}",
            "state": "new",
            "state_label": "New",
            "payment_status": "not_yet_paid",
            "payment_status_label": "Not Yet Paid",
            "total_cost": 500000.0,
            "paid_amount": 0.0,
            "remaining_amount": 500000.0,
            "progress_percentage": 0.0,
            "address": "12 Nguyen Hue, District 1",
            "notes": "Giao truoc 5h chieu",
            "metadata": {{"gift": {{"product_id": 12, "child_name": "Be An"}}}},
            "created_at": "2026-09-22 09:15:00",
            "start_date": "",
            "customer": {{"name": "John Doe", "email": "john@example.com", "phone": "0900000000"}},
            "package": {{"id": {wizard.package_id.id}, "name": "{wizard.package_id.name}"}},
            "services": [
                {{"id": 1, "name": "Service A", "cost": 500000.0, "state": "not_started", "is_selected": true}}
            ]
        }},
        "transaction": {{
            "transaction_id": "TEST_ABC123",
            "payment_state": "pending",
            "amount": 500000.0,
            "status": "pending",
            "is_expired": false,
            "expired_at": "2026-09-22 10:15:00",
            "confirmed_at": "",
            "qr_url": "https://qr.sepay.vn/img?acc=...",
            "payment_url": "",
            "payment_method": {{
                "id": 3, "name": "SePay", "type": "sepay",
                "environment": "live", "image_url": "{wizard.base_url}/web/image/isd_payment.method/3/image"
            }}
        }}
    }}
}}</pre>

    <h4>next_action — what your page should do:</h4>
    <ul>
        <li><code>checkout</code> — the order has no payment yet, send the customer to checkout</li>
        <li><code>wait</code> — a transaction is waiting: show <code>qr_url</code> (scan) or <code>payment_url</code>
            (send the customer to the provider), then poll API 2</li>
        <li><code>recheckout</code> — the transaction is expired, failed or cancelled: create a new one</li>
        <li><code>done</code> — already paid, move the customer to your thank-you page</li>
    </ul>

    <h4>transaction.status values (from the payment system):</h4>
    <ul>
        <li><code>pending</code> / <code>processing</code> — waiting for the money</li>
        <li><code>confirmed</code> — paid</li>
        <li><code>cancelled</code> — replaced by a newer checkout, or cancelled by staff</li>
        <li><code>expired</code> / <code>failed</code> — unusable, start a new payment</li>
    </ul>
    <p><code>transaction</code> is <code>null</code> when the order has no payment at all.</p>

    <h4>Error Response:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #e74c3c;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": false,
        "error": "Order not found",
        "error_code": "ORDER_NOT_FOUND"
    }}
}}</pre>
    <p>Error codes: <code>MISSING_ORDER_REFERENCE</code>, <code>INVALID_USER_PROFILE_ID</code>,
    <code>ORDER_NOT_FOUND</code>, <code>INTERNAL_ERROR</code>.</p>

    <h4>Example cURL:</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/order-info' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "user_profile_id": 456
    }}
  }}'</pre>

    <h4 style="color: #e67e22;">⚠️ Note:</h4>
    <div style="background-color: #fff3cd; padding: 10px; border-left: 3px solid #e67e22; margin-top: 10px;">
        A cancelled QR code or payment link can still be paid at every provider except ACB.
        If that happens the money is picked up automatically within the hour and the order
        turns to <code>done</code> — so treat <code>recheckout</code> as "offer a new payment",
        not as "the old money is lost".
    </div>
</div>
'''

            # API 5: Create Payment on an existing order
            wizard.api_create_payment_doc = f'''
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">🔁 API 5: Create Payment</h3>
    <p>Starts a new payment on an order that already exists. Use it when API 4 answers
    <code>recheckout</code>, or when the customer picks another payment method.</p>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/create-payment
    </div>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">
{{
    "jsonrpc": "2.0",
    "params": {{
        "order_code": "BP_XXX",
        "payment_method_id": 3
    }}
}}</pre>

    <h4>Parameters:</h4>
    <ul>
        <li><strong>order_code</strong>: the code the customer sees. <code>user_profile_id</code> is accepted instead.</li>
        <li><strong>payment_method_id</strong> (required): from <code>payment_methods</code> in the Package Info API.</li>
        <li><strong>half_payment</strong> (optional, default false): collect half of what is left, for a deposit. The rest is collected by calling this again later.</li>
    </ul>

    <div style="background-color: #fff3cd; padding: 10px; border-left: 3px solid #e67e22; margin: 10px 0;">
        <strong>The previous transaction is cancelled first</strong>, so the customer never
        holds two live QR codes. No new order is created: the payment is attached to the
        order you named, for its remaining amount.
    </div>

    <h4>Success Response (200 OK):</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">
{{
    "jsonrpc": "2.0",
    "result": {{
        "success": true,
        "user_profile_id": 456,
        "order_code": "BP_XXX",
        "transaction_id": "BP_YYY",
        "amount": 1650000,
        "expired_at": "2026-09-29 10:15:00",
        "qr_url": "https://qr.sepay.vn/img?acc=..."
    }}
}}</pre>
    <p><code>qr_url</code> comes back for QR gateways, <code>redirect_url</code> for PayPal and VNPay,
    and <code>amount_usd</code> when the gateway charges in USD. Same shape as API 1.</p>

    <h4>Error Codes:</h4>
    <ul>
        <li><code>MISSING_ORDER_REFERENCE</code> — neither order_code nor user_profile_id was sent</li>
        <li><code>ORDER_NOT_FOUND</code> — no order matches</li>
        <li><code>ORDER_CANCELLED</code> — the order was cancelled and cannot be paid</li>
        <li><code>ALREADY_PAID</code> — nothing left to pay, send the customer to your thank-you page</li>
        <li><code>PAYMENT_METHOD_NOT_FOUND</code> — unknown payment_method_id</li>
        <li><code>PAYMENT_METHOD_NOT_ALLOWED</code> — that method belongs to the other environment
            (live methods serve a Live package, test methods a Demo one)</li>
        <li><code>INVALID_AMOUNT</code> — the remaining amount is zero or negative</li>
    </ul>

    <h4>Example cURL:</h4>
    <pre style="background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px;">
curl -X POST '{wizard.base_url}/api/profile/create-payment' \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "jsonrpc": "2.0",
    "params": {{
      "order_code": "BP_XXX",
      "payment_method_id": 3
    }}
  }}'</pre>
</div>
'''

            # API 6: Payment Webhook (receiver)
            wizard.api_payment_webhook_doc = f"""
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">📥 API 6: Payment Webhook</h3>
    <p><b>Only needed when the payment system runs on another server.</b> Sharing one Odoo
    with it, a confirmed payment reaches the order directly and nothing here applies.</p>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {webhook_base}/api/profile/payment-webhook
    </div>

    <h4>Setup</h4>
    <ol>
        <li>Settings &gt; Profile Management &gt; <b>Payment Webhook</b>: press <b>Generate Secret</b>.</li>
        <li>Copy the URL and the secret into <b>Notify URL</b> and <b>Notify Secret</b> on the
            payment method, over in ISD Payment.</li>
    </ol>

    <h4>Headers</h4>
    <ul>
        <li><code>X-ISD-Event</code>: what happened, one of
            <code>transaction.confirmed</code>, <code>transaction.cancelled</code>,
            <code>transaction.expired</code>, <code>transaction.failed</code>. Only
            <code>transaction.confirmed</code> moves the order; the rest answer
            <code>200</code> with <code>ignored</code> so the sender stops retrying.</li>
        <li><code>X-ISD-Signature</code>: HMAC-SHA256 of the raw body, keyed with the secret.
            A call without a matching signature is refused with <code>401</code>.</li>
    </ul>

    <h4>Body</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">{{
    "event": "transaction.confirmed",
    "transaction_id": "BP_7XK2M9QW",
    "status": "confirmed",
    "amount": 1650000,
    "confirmed_at": "2026-09-29 10:15:00",
    "payment_method": {{"id": 3, "name": "SePay", "type": "sepay"}}
}}</pre>

    <h4>Response</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">{{
    "success": true, "matched": true, "confirmed": 1, "payment_status": "paid"
}}</pre>
    <p>The order is set to <b>Paid</b> when the confirmed payments cover the total, and to
    <b>Half Paid</b> when they cover part of it. A transaction belonging to some other system
    answers <code>matched: false</code> with <code>200</code>, and a payment already confirmed
    is left alone: retries are safe.</p>
</div>
"""


            # API 7: Cancel Order
            wizard.api_cancel_order_doc = f"""
<div style="font-family: monospace; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
    <h3 style="color: #2c3e50;">🚫 API 7: Cancel Order</h3>
    <p>Gives up an order nobody paid for, and puts its child back on offer. This is what a
    <b>Back</b> button on the checkout page should call: once an order exists the child is
    already reserved, so going back without cancelling would leave the customer blocked by
    their own order.</p>

    <h4>Endpoint:</h4>
    <div style="background-color: #34495e; color: #ecf0f1; padding: 10px; border-radius: 3px; margin-bottom: 10px;">
        POST {wizard.base_url}/api/profile/cancel-order
    </div>

    <h4>Request Body:</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #3498db;">{{
    "jsonrpc": "2.0",
    "params": {{
        "order_code": "KXM7PQR4TZWD"
    }}
}}</pre>

    <h4>Response</h4>
    <pre style="background-color: white; padding: 10px; border-left: 3px solid #27ae60;">{{
    "success": true
}}</pre>
    <p>An order that was already cancelled answers <code>success: true</code> with
    <code>already_cancelled: true</code>, so pressing Back twice is harmless.</p>

    <h4>Error Codes:</h4>
    <ul>
        <li><code>order_not_found</code> — no order matches that code</li>
        <li><code>order_paid</code> — money was received, so the order stands. Returned as well
            when the gateway has confirmed the transaction but the payment here has not caught
            up yet, which is what a customer pressing Back at the exact moment they pay would
            otherwise slip through.</li>
    </ul>

    <h4>What it does, all in one step</h4>
    <ol>
        <li>Cancels whatever transaction is still waiting, at the gateway too where that is possible</li>
        <li>Moves the order to Cancelled, along with its steps</li>
        <li>Puts <code>metadata.gift.product_id</code> back on offer, if the order carried one</li>
    </ol>
    <p>Releasing the child without cancelling the order is deliberately not offered: a second
    customer could pay for a child the first still holds a payment link for.</p>
</div>
"""


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
