# from typing import List

# import requests
# from requests.adapters import HTTPAdapter
# from urllib3.util.retry import Retry


# def get_session_request(
#     retries: int = 3,
#     backoff_factor: int = 1,
#     retry_statuslist: List[int] = [400, 502, 503, 504],
# ) -> requests.Session:
#     DEFAULT_REQUEST_RETRIES = Retry(
#         total=retries,
#         backoff_factor=backoff_factor,
#         status_forcelist=retry_statuslist,
#     )

#     s = requests.Session()
#     s.mount("http://", HTTPAdapter(max_retries=DEFAULT_REQUEST_RETRIES))
#     return s
