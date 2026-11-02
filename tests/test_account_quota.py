from common.http_client import HttpClient


def test_query_account_quota_returns_totals(api: HttpClient):
    payload = {"userId": "xiaofuge", "activityId": 100301}
    resp = api.request("activity/query_account_quota", payload)

    assert resp.status_code == 200, "HTTP 状态应为 200"
    body = resp.json()
    assert body["code"] == "0000", f"应返回调用成功，实际 {body}"
    data = body["data"]
    assert data["userId"] == payload["userId"]
    assert data["activityId"] == payload["activityId"]
    # 剩余额度不可能超出总额度，且一定 >= 0
    assert 0 <= data["totalCountSurplus"] <= data["totalCount"]
    assert 0 <= data["dayCountSurplus"] <= data["dayCount"]
    assert 0 <= data["monthCountSurplus"] <= data["monthCount"]


def test_query_account_quota_nonexistent_user_returns_error(api: HttpClient):
    payload = {"userId": "nonexistent_user_xyz", "activityId": 100301}
    resp = api.request("activity/query_account_quota", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != "0000", "不存在的用户不应返回成功"
