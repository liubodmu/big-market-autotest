"""错误推测：真实接口对非法输入的容错能力（用例基于探针确认的真实行为）。"""

from common.http_client import HttpClient


def test_partake_empty_user_returns_error(api: HttpClient):
    payload = {"userId": "", "activityId": 100301}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "ERR_BIZ_006", f"空 userId 应落到账户额度校验，实际 {body}"


def test_partake_oversize_user_returns_error(api: HttpClient):
    payload = {"userId": "x" * 200, "activityId": 100301}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "ERR_BIZ_006", f"超长 userId 不应导致系统异常，实际 {body}"
