import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.db import DbClient
from common.http_client import HttpClient


@pytest.fixture(scope="session")
def api():
    client = HttpClient()
    yield client
    client.close()


@pytest.fixture(scope="session")
def db() -> DbClient:
    return DbClient()


@pytest.fixture(scope="session", autouse=True)
def xiaofuge_baseline(db: DbClient):
    """会话开始把 xiaofuge 三层额度统一重置，结束后按快照完整还原。

    避免上次运行遗留的月/日额度 0 污染本次运行（测试可重复的关键）。
    """
    snapshot = db.snapshot_user("xiaofuge", 100301)
    main = snapshot.get("main") or {"total_count": 1389}
    db.reset_partake_user("xiaofuge", 100301, counts=main["total_count"])
    yield
    db.restore_user("xiaofuge", 100301, snapshot)
