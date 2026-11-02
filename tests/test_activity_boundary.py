from datetime import datetime, timedelta
import time

import pytest

from common.config import MASTER_DB_CONFIG
from common.db import DbClient
from common.http_client import HttpClient


# raffle_activity.uq_strategy_id 唯一约束，同一策略只能挂一个活动；
# 每个测试活动需要独立的策略号占位（不会真正参与装配）。
NOTOPEN_STRATEGY_ID = 999997
EXPIRED_STRATEGY_ID = 999998


@pytest.fixture(scope="module")
def boundary_activities():
    """制造两个会话专属测试活动：一个未开启、一个过期；用后清理。"""
    master = DbClient(MASTER_DB_CONFIG)

    def next_free_id():
        for _ in range(20):
            seed = int(time.time() * 1000) % 90000000 + int(time.time() * 17) % 97
            candidate = 910000000 + seed
            if master.get_activity(candidate) is None:
                return candidate
        raise RuntimeError("failed to allocate unique test activity id")

    notopen_id = next_free_id()
    expired_id = next_free_id()

    fmt = "%Y-%m-%d %H:%M:%S"
    now = datetime.now()
    master.insert_test_activity(
        notopen_id,
        "pytest-activity-not-open",
        "close",
        now.strftime(fmt),
        (now + timedelta(days=1)).strftime(fmt),
        NOTOPEN_STRATEGY_ID,
    )
    master.insert_test_activity(
        expired_id,
        "pytest-activity-expired",
        "open",
        (now - timedelta(days=10)).strftime(fmt),
        (now - timedelta(days=1)).strftime(fmt),
        EXPIRED_STRATEGY_ID,
    )

    yield {"notopen": notopen_id, "expired": expired_id}

    master.delete_test_activity(notopen_id)
    master.delete_test_activity(expired_id)


def test_partake_activity_not_open(boundary_activities, api: HttpClient):
    activity_id = boundary_activities["notopen"]
    payload = {"userId": "xiaofuge", "activityId": activity_id}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "ERR_BIZ_003", f"活动非 open 状态应返回 ERR_BIZ_003，实际 {body}"


def test_partake_activity_expired(boundary_activities, api: HttpClient):
    activity_id = boundary_activities["expired"]
    payload = {"userId": "xiaofuge", "activityId": activity_id}
    resp = api.request("activity/partake", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "ERR_BIZ_004", f"活动过期应返回 ERR_BIZ_004，实际 {body}"
