# -*- coding: utf-8 -*-
# This module previously contained PaymentService, PaymentServiceFactory and related
# provider-specific implementations (VTCPay, SePay, PayPal).
#
# Those implementations have been removed as part of the refactor that delegates
# all payment creation and confirmation to the isd_payment module via its REST API:
#   POST /api/payment/{method_id}/create
#   POST /api/payment/{method_id}/confirm
#
# The constants below are retained for reference only.

VTC_PAY_PROVIDER = "vtcpay"
SE_PAY_PROVIDER = "sepay"
PAYPAL_PROVIDER = "paypal"
