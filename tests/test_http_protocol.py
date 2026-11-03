from common.http_client import HttpClient


def test_partake_post_only(api: HttpClient):
    resp = api.raw_request("activity/partake", method="GET")
    assert resp.status_code == 405


def test_malformed_json_returns_400(api: HttpClient):
    resp = api.raw_request(
        "activity/partake",
        method="POST",
        data="{bad json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_partake_missing_activity_id_returns_un_error(api: HttpClient):
    resp = api.request("activity/partake", {"userId": "xiaofuge"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0001", f"缺 activityId 应返回 0001，实际 {body}"
