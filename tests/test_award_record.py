from common.http_client import HttpClient


def test_query_user_award_record(api: HttpClient):
    payload = {"userId": "xiaofuge", "activityId": 100301}
    resp = api.request("activity/query_user_award_record", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000"
    records = body["data"]
    assert isinstance(records, list), "中奖记录应返回列表"
    for record in records:
        assert record["awardId"] > 0
        assert record["awardTitle"], "奖品标题不应为空"
        assert record["awardState"] in ("create", "complete", "fail")


def test_query_user_award_record_invalid_activity_returns_empty(api: HttpClient):
    payload = {"userId": "xiaofuge", "activityId": 999999}
    resp = api.request("activity/query_user_award_record", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000"
    assert body["data"] == [], f"无效活动应返回空列表而非报错，实际 {body}"
