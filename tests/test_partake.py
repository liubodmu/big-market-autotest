from common.db import DbClient
from common.http_client import HttpClient


def test_partake_creates_order(api: HttpClient):
    payload = {"userId": "xiaofuge", "activityId": 100301}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000", f"应返回调用成功，实际 {body}"
    data = body["data"]
    assert data["orderId"], "应返回抽奖订单号"
    assert data["userId"] == payload["userId"]
    assert data["activityId"] == payload["activityId"]
    assert data["strategyId"] == 100006


def test_partake_order_and_quota_consistency(api: HttpClient, db: DbClient):
    """验证参与抽奖接口调用后，额度扣减与订单落库的一致性。"""
    user_id = "xiaofuge"
    activity_id = 100301

    before = db.get_account_quota(user_id, activity_id)
    assert before is not None, f"应存在账户额度记录 userId={user_id} activityId={activity_id}"

    reused = db.find_unused_order(user_id, activity_id)

    payload = {"userId": user_id, "activityId": activity_id}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000", f"应返回调用成功，实际 {body}"
    data = body["data"]
    assert data["strategyId"] == 100006
    order_id = data["orderId"]
    assert order_id, "应返回抽奖订单号"

    row = db.find_order_row(order_id)
    assert row is not None, f"抽奖订单 {order_id} 应在 user_raffle_order_XXX 中落库"
    assert row["order_state"] == "create", f"新订单状态应为 create，实际 {row['order_state']}"

    after = db.get_account_quota(user_id, activity_id)
    if reused and reused["order_id"] == order_id:
        # 复用既有未使用订单时不应扣减额度
        assert after == before, f"复用未使用订单时额度不应变化，实际 {before} -> {after}"
    else:
        assert after["total_count_surplus"] == before["total_count_surplus"] - 1, "总额度应扣减 1"
        assert after["day_count_surplus"] == before["day_count_surplus"] - 1, "日额度应扣减 1"
        assert after["month_count_surplus"] == before["month_count_surplus"] - 1, "月额度应扣减 1"


def test_partake_invalid_activity_returns_error(api: HttpClient):
    payload = {"userId": "xiaofuge", "activityId": 999999}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != "0000", "无效活动不应返回成功"
    assert body["info"], "错误分支应返回失败信息"


def test_partake_full_quota_scenario(api: HttpClient, db: DbClient):
    """场景法：额度耗尽闭环。"""
    user_id = "xiaofuge"
    activity_id = 100301

    snapshot = db.snapshot_user(user_id, activity_id)

    try:
        db.reset_partake_user(user_id, activity_id, counts=5)

        seen_orders = []
        for index in range(1, 6):
            resp = api.request("activity/partake", {"userId": user_id, "activityId": activity_id})
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == "0000", f"第 {index} 次抽奖应成功，实际 {body}"
            order_id = body["data"]["orderId"]
            assert order_id not in seen_orders, f"第 {index} 次抽奖应产生新订单，实际复用 {order_id}"
            seen_orders.append(order_id)

            row = db.find_order_row(order_id)
            assert row is not None, f"订单 {order_id} 应落库"
            assert row["order_state"] == "create"

            # 模拟真实抽奖链路：抽奖成功后订单由 create 变为 used，
            # 否则下一次 partake 会一直复用这张未使用订单。
            assert db.mark_order_used(order_id), f"应能把上一张单置为 used"

            quota = db.get_account_quota(user_id, activity_id)
            assert quota["total_count_surplus"] == 5 - index
            assert quota["day_count_surplus"] == 5 - index
            assert quota["month_count_surplus"] == 5 - index

        final_quota = db.get_account_quota(user_id, activity_id)
        assert final_quota["total_count_surplus"] == 0

        failed = api.request("activity/partake", {"userId": user_id, "activityId": activity_id})
        failed_body = failed.json()
        assert failed_body["code"] == "ERR_BIZ_006", f"额度耗尽应返回 ERR_BIZ_006，实际 {failed_body}"
    finally:
        db.restore_user(user_id, activity_id, snapshot)
