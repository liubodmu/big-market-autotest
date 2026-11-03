"""跨用户隔离测试：user_b 的参与不应影响 xiaofuge 的任何状态。"""

from common.db import DbClient
from common.http_client import HttpClient


USER_ID = "xiaofuge"
OTHER_USER = "pytest_user_b"
ACTIVITY_ID = 100301


def test_partake_cross_user_quota_isolated(api: HttpClient, db: DbClient):
    snapshot_xiaofuge = db.snapshot_user(USER_ID, ACTIVITY_ID)
    snapshot_other = db.snapshot_user(OTHER_USER, ACTIVITY_ID)

    try:
        db.reset_partake_user(OTHER_USER, ACTIVITY_ID, counts=2)
        before_xiaofuge = db.get_account_quota(USER_ID, ACTIVITY_ID)

        resp = api.request("activity/partake", {"userId": OTHER_USER, "activityId": ACTIVITY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000", f"OTHER_USER 抽奖应成功，实际 {body}"

        after_xiaofuge = db.get_account_quota(USER_ID, ACTIVITY_ID)
        assert after_xiaofuge == before_xiaofuge, (
            f"OTHER_USER 参与不应影响 xiaofuge，实际 {before_xiaofuge} -> {after_xiaofuge}"
        )

        after_other = db.get_account_quota(OTHER_USER, ACTIVITY_ID)
        assert after_other["total_count_surplus"] == 1, (
            f"OTHER_USER 参与后额度应为 1，实际 {after_other}"
        )
    finally:
        db.restore_user(USER_ID, ACTIVITY_ID, snapshot_xiaofuge)
        db.restore_user(OTHER_USER, ACTIVITY_ID, snapshot_other)


def test_partake_order_belongs_to_caller(api: HttpClient, db: DbClient):
    snapshot_other = db.snapshot_user(OTHER_USER, ACTIVITY_ID)

    try:
        db.reset_partake_user(OTHER_USER, ACTIVITY_ID, counts=2)
        resp = api.request("activity/partake", {"userId": OTHER_USER, "activityId": ACTIVITY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000", f"OTHER_USER 抽奖应成功，实际 {body}"

        order_id = body["data"]["orderId"]
        row = db.find_order_row(order_id)
        assert row is not None, f"应能找到订单 {order_id}，实际 {row}"
        assert row["user_id"] == OTHER_USER, f"订单应归属 OTHER_USER，实际 {row}"
        assert row["activity_id"] == ACTIVITY_ID, f"订单应挂在该活动，实际 {row}"
    finally:
        db.restore_user(OTHER_USER, ACTIVITY_ID, snapshot_other)


def test_partake_cross_user_unused_order_untouched(api: HttpClient, db: DbClient):
    snapshot_other = db.snapshot_user(OTHER_USER, ACTIVITY_ID)

    try:
        db.reset_partake_user(OTHER_USER, ACTIVITY_ID, counts=2)
        resp = api.request("activity/partake", {"userId": OTHER_USER, "activityId": ACTIVITY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000", f"OTHER_USER 抽奖应成功，实际 {body}"

        # OTHER_USER 参与后应有一张 create 状态的未使用订单，且归属本身
        unused_after = db.find_unused_order(OTHER_USER, ACTIVITY_ID)
        assert unused_after is not None, f"OTHER_USER 应出现未使用订单，实际 {unused_after}"
        assert unused_after["order_id"] == body["data"]["orderId"], (
            f" OTHER_USER 未使用订单应与本次订单一致，实际 {unused_after}"
        )
    finally:
        db.restore_user(OTHER_USER, ACTIVITY_ID, snapshot_other)
