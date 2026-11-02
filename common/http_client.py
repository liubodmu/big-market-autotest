import requests

from common.config import API_PREFIX, BASE_URL


class HttpClient:
    """Wraps a requests session with the service base url and API prefix."""

    def __init__(self, base_url: str = BASE_URL, prefix: str = API_PREFIX):
        self.base_url = base_url.rstrip("/")
        self.prefix = prefix
        self.session = requests.Session()

    def request(self, path: str, payload: dict | None = None, method: str = "POST",
                params: dict | None = None):
        url = f"{self.base_url}{self.prefix}/{path.lstrip('/')}"
        return self.session.request(
            method=method,
            url=url,
            json=payload,
            params=params,
            timeout=10,
        )

    def raw_request(self, path: str, method: str = "POST", **kwargs):
        """不做任何封装的原始请求，供协议级异常用例使用。"""
        url = f"{self.base_url}{self.prefix}/{path.lstrip('/')}"
        return self.session.request(method=method, url=url, timeout=10, **kwargs)

    def close(self):
        self.session.close()
