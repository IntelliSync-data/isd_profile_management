
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid
from odoo import tools

import pytz
import requests
from requests.adapters import HTTPAdapter
import urllib.parse
from urllib3 import Retry

VTC_PAY_PROVIDER = "vtcpay"
SE_PAY_PROVIDER = "sepay"
PAYPAL_PROVIDER = "paypal"

def get_session_request(
    retries: int = 3,
    backoff_factor: int = 1,
    retry_statuslist: List[int] = [400, 502, 503, 504],
) -> requests.Session:
    DEFAULT_REQUEST_RETRIES = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=retry_statuslist,
    )

    s = requests.Session()
    s.mount("http://", HTTPAdapter(max_retries=DEFAULT_REQUEST_RETRIES))
    return s


def calc_md5_hash(*args):
    in_encode_md5: str = ""
    for a in args:
        in_encode_md5 += a

    return hashlib.md5(in_encode_md5.encode("utf-8")).hexdigest()


def parse_int(num_string: Optional[Any], default: int = -1) -> int:
    try:
        return int(float(num_string))  # type: ignore
    except:
        return default


class BaseEnum(Enum):
    def __eq__(self, value):
        if isinstance(self.value, value.__class__):
            return self.value == value

        return super().__eq__(value)

    @classmethod
    def to_choices(cls) -> tuple:
        result: List[Any] = []
        for mem in dict(cls.__members__).values():
            result.append((mem.value, mem.name))

        return tuple(result)

    @classmethod
    def switcher(cls):
        result: Dict[Any, Any] = {}
        for mem in dict(cls.__members__).values():
            result.update({mem.value: mem.name})

        return result


@dataclass
class CreatePGPaymentResDto:
    transaction_id: str
    redirect_url: Optional[str] = None
    qr_url: Optional[str] = None


@dataclass
class ConfirmPGPaymentResDto:
    class Status(BaseEnum):
        ACTIVE = "active"
        IN_REVIEW = "in_review"
        IN_CHECKING = "in_checking"
        PROCESSING = "processing"
        FAILURE = "failure"

        def __str__(self) -> str:
            return self.value

    status: str = Status.ACTIVE.value
    message: str = ""


@dataclass
class ConfirmPGPaymentReqDto:
    amount: float
    payment_parameters: Optional[str] = None


class PaymentService:
    def __init__(self, env) -> None:
        self.db_env = env

    def create_payment(self, amount, currency, ipn_url, **kwargs) -> CreatePGPaymentResDto:
        # Implementation for creating a payment
        raise NotImplementedError()

    def confirm_payment(self, transaction_id: str, dto: ConfirmPGPaymentReqDto) -> ConfirmPGPaymentResDto:
        # Implementation for confirming a payment
        raise NotImplementedError()


class VTCPayPaymentService(PaymentService):
    _host: str = ""
    _key_sign = ""
    _website_id: str = ""
    _security_code: str = ""
    _payment_type: str = ""
    _revceiver_account: str = ""

    def _init_params(self):
        ir_config_params = self.db_env['ir.config_parameter'].sudo()

        self._host = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_host')
        self._key_sign = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_key_sign')
        self._website_id = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_website_id')
        self._security_code = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_security_code')
        self._payment_type = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_payment_type')
        self._revceiver_account = ir_config_params.get_param(
            'isd_profile_management.pm_vtcpay_revceiver_account')

    def create_payment(self, amount, currency, ipn_url, **kwargs):
        self._init_params()
        # Implementation for creating a VTC Pay payment
        transaction_id: str = str(uuid.uuid4())
        amount = int(amount) * 1000

        query_params: Dict[str, Optional[str]] = {
            "amount": str(amount),
            "bill_to_email": "",  # TODO: get from user data
            "bill_to_phone": "",  # TODO: get from user data
            "currency": "VND",
            "language": "vi",
            "payment_type": self._payment_type or "DomesticBank",
            "reference_number": transaction_id,
            "url_return": urllib.parse.unquote_plus(ipn_url),
            "website_id": self._website_id,
            "country": "VN",
        }
        for _key in list(query_params.keys()):
            if query_params[_key] is None:
                query_params.pop(_key)

        signature_pattern: str = "amount|bill_to_email|bill_to_phone|country|currency|language|payment_type|reference_number|url_return|website_id"
        signature_values: List[str] = []
        for k in signature_pattern.split("|"):
            if k in query_params:
                signature_values.append(query_params[k] or "")

        signature_values.append(self._security_code)
        signature = hashlib.sha256(
            "|".join(signature_values).encode()).hexdigest()
        query_params.update({"signature": signature})

        pay_url: str = f"{self._host}/checkout.html?" + "&".join(
            list(
                map(
                    lambda x: f"{x}={urllib.parse.quote_plus(query_params[x] or '')}",
                    query_params,
                )
            )
        )

        return CreatePGPaymentResDto(
            transaction_id=transaction_id,
            redirect_url=pay_url
        )

    def confirm_payment(self, transaction_id: str, dto: ConfirmPGPaymentReqDto) -> ConfirmPGPaymentResDto:
        self._init_params()
        
        order_status: int = -1
        if dto.payment_parameters:
            payment_parameters = dto.payment_parameters
            assert payment_parameters is not None, "Missing Payment Parameters"

            params: Dict[str, str] = {}
            for _part in payment_parameters.split("&"):
                _k, _v = _part.split("=")

                params[_k] = _v

            signature_pattern: str = "amount|message|payment_type|reference_number|status|trans_ref_no|website_id"
            signature_values: List[str] = []
            for k in signature_pattern.split("|"):
                signature_values.append(params[k])

            signature_values.append(self._security_code)

            signature: str = params["signature"].lower()
            calc_signature: str = hashlib.sha256(
                "|".join(signature_values).encode()
            ).hexdigest()

            if signature != calc_signature:
                raise Exception("The signature is invalid")

            amount = dto.amount
            amount = int(amount) * 1000
            if parse_int(params["amount"]) != amount:
                raise Exception("Số tiền giao dịch không đúng")

            order_status = parse_int(params["status"], -1)
        else:
            signature: str = calc_md5_hash(
                self._key_sign,
                self._revceiver_account,
                self._website_id,
                "WEBSITE",
                self._security_code,
            )

            url = f"{self._host}/api/AccountApi/VTCPayGetOrderStatus"

            payload = json.dumps(
                {
                    "merchantType": "WEBSITE",
                    "intergratedID": self._website_id,
                    "revceiverAccount": self._revceiver_account,
                    "sign": signature,
                    "listMerchantOrderCode": [{"orderCode": transaction_id}],
                }
            )
            headers = {"Content-Type": "application/json"}

            s = get_session_request()
            response = s.post(url, headers=headers, data=payload)

            res_data: Dict[str, Any] = response.json()
            if not res_data["ListOrderStatus"]:
                raise Exception("Order not found!")

            order_data: Dict[str, Any] = res_data["ListOrderStatus"][0]
            order_status = order_data["Status"]

        msg = self.errors_mapper().get(order_status, "Lỗi không được xác định")
        if order_status not in [1, 7, -99]:
            raise Exception(msg)

        pg_status: str = str(ConfirmPGPaymentResDto.Status.ACTIVE)
        if order_status == 7:
            pg_status = str(ConfirmPGPaymentResDto.Status.IN_REVIEW)
        elif order_status == -99:
            pg_status = str(ConfirmPGPaymentResDto.Status.IN_CHECKING)

        # Implementation for confirming a VTC Pay payment
        return ConfirmPGPaymentResDto(
            status=pg_status,
            message=msg
        )

    @staticmethod
    def errors_mapper() -> Dict[int, str]:
        return {
            0: "Giao dịch ở trạng thái khởi tạo",
            # 1	SUCCESS	Giao dịch thành công
            7: "Tài khoản thanh toán của khách hàng đã bị trừ tiền nhưng tài khoản của Merchant chưa được cộng tiền. Bộ phận quản trị thanh toán của VTC sẽ duyệt để quyết định giao dịch thành công hay thất bại",
            -1: "Giao dịch thất bại",
            -9: "Bạn đã huỷ giao dịch",
            -3: "Quản trị VTC hủy giao dịch",
            -4: "Thẻ/tài khoản không đủ điều kiện giao dịch (Đang bị khóa, chưa đăng ký thanh toán online …)",
            -5: "Số dư tài khoản của bạn không đủ để thực hiện giao dịch. Vui lòng kiểm tra và thử lại",
            -6: "Hệ thống đang xảy ra lỗi, vui lòng thử lại sau",
            -7: "Khách hàng nhập sai thông tin thanh toán ( Sai thông tin tài khoản hoặc sai OTP)",
            -8: "Bạn đã quá hạn mức thanh toán trong ngày. Vui lòng kiểm tra và thử lại",
            -22: "Số tiền thanh toán đơn hàng quá nhỏ",
            -24: "Đơn vị tiền tệ thanh toán đơn hàng không hợp lệ. Vui lòng kiểm tra và thử lại",
            -25: "Có lỗi xảy ra trong quá trình giao dịch, vui lòng thử lại sau",
            -28: "Thiếu tham số bắt buộc phải có trong một đơn hàng thanh toán online",
            -29: "Tham số request không hợp lệ",
            -21: "Có lỗi xảy ra trong quá trình giao dịch. Vui lòng thử lại sau",
            -23: "WebsiteID không tồn tại",
            -99: "Có lỗi xảy ra trong quá trình giao dịch, Vui lòng liên hệ qua số điện thoại 19001878 để được hỗ trợ nếu bạn đã bị trừ tiền",
        }


class SePayPaymentService(PaymentService):
    _host: str = ""
    _qr_host: str = ""
    _acc_number: str = ""
    _acc_bank: str = ""
    _api_token: str = ""

    _prefix_transaction_id: str = ""

    def _init_params(self):
        ir_config_params = self.db_env['ir.config_parameter'].sudo()
        self._host = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_host')
        self._qr_host = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_qr_host')
        self._acc_number = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_acc_number')
        self._acc_bank = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_acc_bank')
        self._api_token = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_api_token')
        self._prefix_transaction_id = ir_config_params.get_param(
            'isd_profile_management.pm_sepay_prefix_transaction_id')

    def id_gen(self) -> str:

        import secrets
        import string

        ALPHABET = string.ascii_letters + string.digits  # base62

        length: int = 10
        return self._prefix_transaction_id + ''.join(secrets.choice(ALPHABET) for _ in range(length))

    def create_payment(self, amount, currency, ipn_url, **kwargs) -> CreatePGPaymentResDto:
        self._init_params()

        amount = int(amount) * 1000

        transaction_id: str = self.id_gen()
        qr_url: str = f"{self._qr_host}/img?acc={self._acc_number}&bank={self._acc_bank}&amount={amount}&des={transaction_id}"

        return CreatePGPaymentResDto(
            transaction_id=transaction_id,
            qr_url=qr_url
        )

    def confirm_payment(self, transaction_id: str, dto: ConfirmPGPaymentReqDto) -> ConfirmPGPaymentResDto:
        self._init_params()

        amount = int(dto.amount) * 1000

        on_date = datetime.now(tz=pytz.timezone('Asia/Ho_Chi_Minh')).date()
        on_date = on_date - timedelta(days=1)
        on_date_str = on_date.strftime('%Y-%m-%d')

        url = f"{self._host}/userapi/transactions/list?transaction_date_min={on_date_str}&amount_in={str(amount)}"

        payload = {}
        headers = {
            'Authorization': 'Bearer {}'.format(self._api_token),
            'Content-Type': 'application/json'
        }

        s = get_session_request()
        response = s.get(url, headers=headers, data=payload)
        if not (300 > response.status_code >= 200):
            raise Exception("Could not retrieve transactions from SePay")

        response_data: Dict[str, Any] = response.json()
        if response_data["status"] != 200:
            raise Exception("Error from SePay: {}".format(
                response_data.get("error", "Unknown error")))

        transactions: List[Dict[str, Any]
                           ] = response_data.get('transactions', [])

        for tx in transactions:
            if tx.get('code') == transaction_id and parse_int(tx.get('amount_in')) == amount:
                status = str(ConfirmPGPaymentResDto.Status.ACTIVE)
                message = "Payment confirmed via SePay"

                return ConfirmPGPaymentResDto(
                    status=status,
                    message=message
                )

        return ConfirmPGPaymentResDto(
            status=ConfirmPGPaymentResDto.Status.PROCESSING.value,
            message="Payment confirmed via SePay"
        )


class PaypalPaymentService(PaymentService):
    _host: str = ""
    _client_id: str = ""
    _client_secret: str = ""
    _mode: str = "sandbox"  # or "live"
    _usd_exchange_rate: float = 26300.0

    def _init_params(self):
        ir_config_params = self.db_env['ir.config_parameter'].sudo()
        self._host = ir_config_params.get_param(
            'isd_profile_management.pm_paypal_host')
        self._client_id = ir_config_params.get_param(
            'isd_profile_management.pm_paypal_client_id')
        self._client_secret = ir_config_params.get_param(
            'isd_profile_management.pm_paypal_client_secret')
        self._mode = ir_config_params.get_param(
            'isd_profile_management.pm_paypal_mode')
        self._usd_exchange_rate = float(ir_config_params.get_param(
            'isd_profile_management.pm_paypal_usd_exchange_rate', default='26300'))
    
    @staticmethod
    def _gen_token(host: str, client_id: str, client_secret: str) -> str:
        gen_token_api: str = f"{host}/v1/oauth2/token"
        
        _headers = {"Accept-Language": "en_US", "Accept": "application/json"}
        
        s = get_session_request()
        response = s.post(
            gen_token_api,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers=_headers,
        )
        if not (300 > response.status_code >= 200):
            raise Exception("Could not generate PayPal access token")
        
        response_data: Dict[str, Any] = response.json()
        access_token: str = response_data.get("access_token", "")
        token_type: str = response_data.get("token_type", "")
        
        if not access_token:
            raise Exception("Could not retrieve PayPal access token")
        
        if token_type == "Bearer":
            return token_type + " " + access_token
        
        return access_token
    
    # @tools.ormcache('client_id', 'expires_in')
    @staticmethod
    def _get_auth_headers(host: str, client_id: str, client_secret, expires_in: int) -> Dict[str, str]:
        return {"Content-type": "application/json", "Authorization": PaypalPaymentService._gen_token(host, client_id, client_secret)}

    def create_payment(self, amount, currency, ipn_url, **kwargs) -> CreatePGPaymentResDto:
        self._init_params()
        
        amount = amount * 1000
        
        order_api: str = f"{self._host}/v2/checkout/orders"
        amount_usd: float = round(amount / self._usd_exchange_rate, 2)
        
        _body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": round(amount_usd, 2),
                    }
                }
            ],
            "application_context": {
                "locale": "en-US",
                "shipping_preference": "NO_SHIPPING",
                "payment_method": {
                    "payer_selected": "PAYPAL",
                    "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
                },
                "return_url": ipn_url,
                "cancel_url": ipn_url,
            },
        }
        
        try:
            s = get_session_request()
            headers = self._get_auth_headers(self._host, self._client_id, self._client_secret, expires_in=3600)
            response = s.post(order_api, headers=headers, json=_body)
            if not (300 > response.status_code >= 200):
                raise Exception("Could not create PayPal order")
            
            response_data: Dict[str, Any] = response.json()
            
            return CreatePGPaymentResDto(
                transaction_id=response_data.get("id", ""),
                redirect_url=next(
                    (
                        link.get("href")
                        for link in response_data.get("links", [])
                        if link.get("rel") == "approve"
                    ),
                    None,
                ),
            )
        except Exception as e:
            raise e
        
        
    def confirm_payment(self, transaction_id: str, dto: ConfirmPGPaymentReqDto) -> ConfirmPGPaymentResDto:
        self._init_params()
        
        capture_api: str = f"{self._host}/v2/checkout/orders/{transaction_id}/capture"
        
        try:
            s = get_session_request()
            headers = self._get_auth_headers(self._host, self._client_id, self._client_secret, expires_in=3600)
            response = s.post(capture_api, headers=headers)
            if not (300 > response.status_code >= 200):
                raise Exception("Could not capture PayPal order")
            
            response_data: Dict[str, Any] = response.json()
            status: str = response_data.get("status", "")
            if status != "COMPLETED":
                raise Exception(f"Payment not completed, current status: {status}")
            
            return ConfirmPGPaymentResDto(
                status=ConfirmPGPaymentResDto.Status.ACTIVE.value,
                message="Payment confirmed via PayPal"
            )
        except Exception as e:
            raise e

class PaymentServiceFactory:
    @staticmethod
    def create(provider: str, env) -> PaymentService:
        if provider == VTC_PAY_PROVIDER:
            return VTCPayPaymentService(env)
        elif provider == SE_PAY_PROVIDER:
            return SePayPaymentService(env)
        elif provider == PAYPAL_PROVIDER:
            return PaypalPaymentService(env)
        else:
            raise ValueError(f"Unsupported payment provider: {provider}")
