# import hashlib
# from typing import Any, Optional

# def calc_md5_hash(*args):
#     in_encode_md5: str = ""
#     for a in args:
#         in_encode_md5 += a

#     return hashlib.md5(in_encode_md5.encode("utf-8")).hexdigest()

# def parse_int(num_string: Optional[Any], default: int = -1) -> int:
#     try:
#         return int(float(num_string))  # type: ignore
#     except:
#         return default
