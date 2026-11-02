import os

BASE_URL = os.environ.get("BIG_MARKET_BASE_URL", "http://127.0.0.1:8091")
API_PREFIX = os.environ.get("BIG_MARKET_API_PREFIX", "/api/v1")

def _schema_split(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]

# db-router 会把 userId 分到 big_market_01 或 big_market_02，
# 测试数据工厂在两个库同时准备同一份数据，保证断言不依赖路由结果。
DB_CONFIG = {
    "host": os.environ.get("BIG_MARKET_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("BIG_MARKET_DB_PORT", "13306")),
    "user": os.environ.get("BIG_MARKET_DB_USER", "root"),
    "password": os.environ.get("BIG_MARKET_DB_PASSWORD", "123456"),
    # db-router 按 userId 分库，xiaofuge 目前落在 big_market_01；如需换 schema 通过环境变量覆盖
    "database": os.environ.get("BIG_MARKET_DB_SCHEMA", "big_market_01"),
}
DB_SCHEMAS = _schema_split(os.environ.get("BIG_MARKET_DB_SCHEMAS", "big_market_01,big_market_02"))

# 活动元数据未分库分表，保存在 big_market 主库
MASTER_DB_SCHEMA = os.environ.get("BIG_MARKET_MASTER_SCHEMA", "big_market")
MASTER_DB_CONFIG = dict(DB_CONFIG)
MASTER_DB_CONFIG["database"] = MASTER_DB_SCHEMA
