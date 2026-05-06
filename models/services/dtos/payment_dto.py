# from dataclasses import dataclass
# from datetime import datetime
# from typing import Optional

# from custom_addons.isd_profile_management.utils.base_enum import BaseEnum



# @dataclass
# class CreatePGPaymentResDto:
#     transaction_id: str
#     redirect_url: Optional[str] = None


# @dataclass
# class ConfirmPGPaymentResDto:
#     class Status(BaseEnum):
#         ACTIVE = "status"
#         IN_REVIEW = "in_review"
#         IN_CHECKING = "in_checking"
#         PROCESSING = "processing"
#         FAILURE = "failure"

#         def __str__(self) -> str:
#             return self.value

#     status: str = Status.ACTIVE.value
#     message: str = ""

# @dataclass
# class ConfirmPGPaymentReqDto:
#     amount: float
#     payment_parameters: Optional[str] = None