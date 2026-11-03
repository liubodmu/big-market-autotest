# big-market-autotest

针对 `big-market` 抽奖业务 REST API 的 pytest + requests 接口自动化测试工程。

## 前置条件

1. big-market 本地服务已启动（默认 `http://127.0.0.1:8091`）。
2. Python 3.10+。

安装依赖：

```bash
pip install -r requirements.txt
```

## 运行

```bash
pytest
```

被测服务地址可覆盖：

```bash
BIG_MARKET_BASE_URL=http://other-host:8091 pytest
```

## CI

`.github/workflows/ci.yml` 会在 push 到 main / PR 时自动执行：

1. 启动 MySQL(13306)/Redis(16379)/RabbitMQ(5672) 三个服务容器
2. 从 `${{ github.repository_owner }}/big-market` 克隆被测工程，并用
   `docs/dev-ops/environment/mysql/sql/big_market.sql` + `big_market_shards.sql`
   和 `big_market_master.sql` 初始化主库、策略/活动元数据和两个分库
3. `mvn package` 编译 `big-market-app.jar` 后台启动，等 `/api/v1/activity/query_account_quota` 通
4. 跑全部 pytest 用例，上传 `reports/junit.xml` 作为流水线产物

## 用例范围

按模块覆盖（42 条设计矩阵见 `docs/test-design.md` 第五节，41 条已落地）：

- `POST /api/v1/activity/partake`，含无效 activityId 的异常分支
- `POST /api/v1/activity/query_account_quota`
- `POST /api/v1/activity/query_user_award_record`
- `GET /api/v1/raffle/strategy_armory`
- `POST /api/v1/raffle/query_raffle_award_list`
- `POST /api/v1/raffle/random_raffle`
- HTTP 协议层异常（405、非法 JSON）
- 数据驱动矩阵：`testdata/readonly_cases.yaml`（11 条只读接口正反用例）
- 跨用户（双用户）隔离场景

完整测试设计见 `docs/test-design.md`（等价类 / 边界值 / 场景法 / 错误推测映射）。

`test_partake_order_and_quota_consistency` 会把接口返回值与 MySQL 落库数据对比：

- 参与抽奖生成的订单必须落在 `user_raffle_order_000..003` 其中一张分表，且状态为 `create`
- 若是新建订单，`raffle_activity_account` 的总/日/月剩余额度应当各扣减 1
- 若接口复用了既有的未使用订单（幂等分支），额度不应变化

## 数据库连接

`common/db.py` 默认连 `127.0.0.1:13306` 的 `big_market_01`（db-router 分库结果）。
如需覆盖，通过以下环境变量：

```bash
BIG_MARKET_DB_HOST=... BIG_MARKET_DB_PORT=... BIG_MARKET_DB_USER=... BIG_MARKET_DB_PASSWORD=... BIG_MARKET_DB_SCHEMA=... pytest
```

## 重复运行说明

`test_partake_*` 用真实用户 xiaofuge 调真实接口，每次运行若没有未使用订单会创建新
订单并扣减 1 次额度。连续跑多次后剩余额度会下降，需要时可用 `BIG_MARKET_DB_SCHEMA`
或新账户来隔离。
