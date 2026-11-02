from datetime import datetime

from common.db import DbClient
from common.http_client import HttpClient


USER_ID = "xiaofuge"
ACTIVITY_ID = 100301


def test_partake_month_quota_exhausted(api: HttpClient, db: DbClient):
    """边界值：总额度充足、月额度为 0，应返回 ERR_BIZ_007。"""
    snapshot = db.snapshot_user(USER_ID, ACTIVITY_ID)
    month = datetime.now().strftime("%Y-%m")

    try:
        db.reset_partake_user(USER_ID, ACTIVITY_ID, counts=5)
        db.seed_account_month(USER_ID, ACTIVITY_ID, month, month_count_surplus=0)

        resp = api.request("activity/partake", {"userId": USER_ID, "activityId": ACTIVITY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "ERR_BIZ_007", f"应为账户月额度不足，实际 {body}"
    finally:
        db.restore_user(USER_ID, ACTIVITY_ID, snapshot)


def test_partake_day_quota_exhausted(api: HttpClient, db: DbClient):
    """边界值：总额度/月额度充足、日额度为 0，应返回 ERR_BIZ_008。"""
    snapshot = db.snapshot_user(USER_ID, ACTIVITY_ID)
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        db.reset_partake_user(USER_ID, ACTIVITY_ID, counts=5)
        db.seed_account_day(USER_ID, ACTIVITY_ID, today, day_count_surplus=0)

        resp = api.request("activity/partake", {"userId": USER_ID, "activityId": ACTIVITY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "ERR_BIZ_008", f"应为账户日额度不足，实际 {body}"
    finally:
        db.restore_user(USER_ID, ACTIVITY_ID, snapshot)
