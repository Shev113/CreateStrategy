"""Общая requests.Session с Retry для MOEX ISS API."""
import requests
import urllib3
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _build_moex_session() -> requests.Session:
    """Сессия requests с Retry для MOEX ISS API."""
    s = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=('GET', 'HEAD'),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    s.headers.update({'User-Agent': 'CreateStrategy/1.0'})
    s.verify = False
    return s


MOEX_SESSION = _build_moex_session()
