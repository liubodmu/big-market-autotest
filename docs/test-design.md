# 测试设计（等价类 / 边界值 / 场景法 / 错误推测）

## 一、功能点清单（先单点，后场景）

| # | 功能点 | 层 | 方法 | 路径 |
|---|---|---|---|---|
| F1 | 策略装配 | HTTP | GET | `/api/v1/raffle/strategy_armory` |
| F2 | 查询奖池 | HTTP | POST | `/api/v1/raffle/query_raffle_award_list` |
| F3 | 随机抽奖 | HTTP | POST | `/api/v1/raffle/random_raffle` |
| F4 | 参与抽奖（建单+扣额度） | HTTP+DB | POST | `/api/v1/activity/partake` |
| F5 | 查询账户额度 | HTTP+DB | POST | `/api/v1/activity/query_account_quota` |
| F6 | 查询中奖记录 | HTTP+DB | POST | `/api/v1/activity/query_user_award_record` |
| D1 | 订单落库 | DB | — | `user_raffle_order_000..003` |
| D2 | 账户额度三层 | DB | — | 总/日/月 `raffle_activity_account*` |

## 二、用例设计映射

### 等价类划分

| 输入参数 | 有效等价类 | 无效等价类 |
|---|---|---|
| strategyId | 已配置策略（100006） | 不存在的策略（当前返回 0000+空列表，已记录为待优化） |
| activityId | 已配置活动（100301） | 不存在的活动 |
| userId | 具有额度的用户 | 不存在的用户、null、超长字符串 |

### 边界值分析

| 观察项 | 边界 | 用例 |
|---|---|---|
| 总额度剩余 | 1（临界可用）/ 0（临界不可用） | 连续抽奖到剩余 0，第 6 次应报 `ERR_BIZ_006` |
| 月额度剩余 | 0（临界不可用） | 造数据插入月额度 = 0，应报 `ERR_BIZ_007` |
| 日额度剩余 | 0（临界不可用） | 造数据插入日额度 = 0，应报 `ERR_BIZ_008` |
| 订单状态 | `create`（未使用 → 复用路径） | 重复调用同一用户应复用而非新建 |
| 账户余额扣减 | 总/日/月三层必须同时 -1 | 场景法逐次断言 |
| 活动状态 | 非 `open`（如 `close`） | 插入 state='close' 的测试活动，应报 `ERR_BIZ_003` |
| 活动日期 | 已过期 | 插入已过期的测试活动，应报 `ERR_BIZ_004` |

### 场景法（业务闭环）

| 场景 | 前置 | 步骤与预期 |
|---|---|---|
| S1 额度耗尽闭环 | 测试用户额度 = 5 | 连续 5 次抽奖全部成功，每次落库+额度均 -1；每轮结束后把上一张单置为 used 以模拟真实链路；第 6 次返回 `ERR_BIZ_006` |
| S2 幂等复用 | 存在未使用订单 | 重复 partake 返回同一 order，额度不变 |
| S3 抽奖命中奖池 | 策略 100006 有 101~108 奖品 | 三次 random_raffle 均命中奖池集合 |

### 数据驱动（YAML）· 只读接口矩阵

只读接口（`query_account_quota` / `query_user_award_record` / `query_raffle_award_list`）
没有副作用，最适合把“输入差异 → 预期差异”这种高频用例抽到 `testdata/readonly_cases.yaml`，
通过 `pytest.mark.parametrize` 一键生成：

| ID | 端点 | 输入 | 预期 |
|---|---|---|---|
| RO-QUOTA-001..005 | query_account_quota | 有效/无效 user、无效/极小 activityId | 0000+字段完整 / ERR_BIZ_006 |
| RO-AWARD-001..003 | query_user_award_record | 有效/空 user、无效 activityId | 0000+记录或空列表 |
| RO-RPOOL-001..003 | query_raffle_award_list | 有效/极小/无效 strategyId | 0000+奖池或空列表 |

> RO-RPOOL-002/003 与 RO-AWARD-002/003 现在都断言“成功码 + 空列表”，这是接口契约现状的快照，
> 若后端改成专用错误码，这两个用例也会随之改写（当前留作观察点，未按缺陷处理）。

## 五、模块级功能矩阵（42 条接口用例）

按被测系统当前真实暴露的 6 个 HTTP 接口 + 3 个 DB 层位（账户/订单/记录）构成，
每行对应仓库里一条已在断言的测试或已固化到 YAML 的数据驱动用例。

### 模块 1 · 策略装配 (raffle/strategy_armory)

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MA-01 | 等价类 | 有效策略 100006 | 0000 + data=true | tests/test_strategy.py::test_strategy_armory_success |
| MA-02 | 场景法 | 双次调用同一策略 | 两次都 0000 + data=true（幂等） | tests/test_armory.py::test_strategy_armory_idempotent |
| MA-03 | 场景法 | 装配后奖池复查 | 奖池 ID 集合与装配前一致 | tests/test_armory.py::test_strategy_armory_does_not_mutate_award_pool |

### 模块 2 · 抽奖 (raffle/query_raffle_award_list + random_raffle)

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MR-01 | 等价类 | 有效策略 | 0000 + 列表字段完备 | tests/test_strategy.py::test_query_raffle_award_list_structure |
| MR-02 | 等价类 | 不存在的策略 | 0000 + 空列表（契约现状，见 B3） | tests/test_strategy.py::test_query_raffle_award_list_invalid_strategy_returns_empty |
| MR-03 | 边界值 | strategyId=1 极小值 | 0000 + 空列表 | testdata/readonly_cases.yaml::RO-RPOOL-003 |
| MR-04 | 错误推测 | strategyId 类型不匹配 | HTTP 400 | testdata/readonly_cases.yaml::RO-RPOOL-004 |
| MR-05 | 错误推测 | body={} 缺参 | 0000 + 空列表（现状，见 B5） | tests/test_strategy.py::test_query_raffle_award_list_missing_payload_returns_empty |
| MR-06 | 场景法 | 三次随机抽奖 | 每次命中奖池 & sort 对齐 | tests/test_strategy.py::test_random_raffle_award_in_strategy_pool |
| MR-07 | 等价类 | 不存在的策略随机抽奖 | 0001 | tests/test_strategy.py::test_random_raffle_invalid_strategy_returns_error |
| MR-08 | 错误推测 | body={} 缺参 | 0002 非法参数 | tests/test_strategy.py::test_random_raffle_missing_body_returns_illegal_parameter |

### 模块 3 · 活动参与 (activity/partake)

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MP-01 | 等价类 | 有效 user+activity | 0000 + orderId | tests/test_partake.py::test_partake_creates_order |
| MP-02 | 场景法 | 订单落库 + 额度扣减一致性 | 订单在分区表中为 create，总/日/月各 -1 | tests/test_partake.py::test_partake_order_and_quota_consistency |
| MP-03 | 等价类 | 不存在的 activityId | 非 0000 | tests/test_partake.py::test_partake_invalid_activity_returns_error |
| MP-04 | 场景法 | 重置额度 5 + 连抽 5 次 + 消耗单 + 第 6 次 | 每次 -1，第 6 次 ERR_BIZ_006 | tests/test_partake.py::test_partake_full_quota_scenario |
| MP-05 | 边界值 | 月额度 = 0 | ERR_BIZ_007 | tests/test_quota_boundary.py::test_partake_month_quota_exhausted |
| MP-06 | 边界值 | 日额度 = 0 | ERR_BIZ_008 | tests/test_quota_boundary.py::test_partake_day_quota_exhausted |
| MP-07 | 边界值 | 活动 state=close | ERR_BIZ_003 | tests/test_activity_boundary.py::test_partake_activity_not_open |
| MP-08 | 边界值 | 活动已过期 | ERR_BIZ_004 | tests/test_activity_boundary.py::test_partake_activity_expired |
| MP-09 | 错误推测 | userId 为空 | ERR_BIZ_006 | tests/test_input_guard.py::test_partake_empty_user_returns_error |
| MP-10 | 错误推测 | userId 200 字符 | ERR_BIZ_006 | tests/test_input_guard.py::test_partake_oversize_user_returns_error |
| MP-11 | 错误推测 | 缺 activityId | 0001 | tests/test_http_protocol.py::test_partake_missing_activity_id_returns_un_error |
| MP-12 | 场景法 | 其他用户参与 | xiaofuge 三层额度不变 | tests/test_partake_cross_user.py::test_partake_cross_user_quota_isolated |
| MP-13 | 场景法 | 其他用户参与 | 订单归属调用方 | tests/test_partake_cross_user.py::test_partake_order_belongs_to_caller |
| MP-14 | 场景法 | 其他用户参与 | 未使用订单 create 且归属调用方 | tests/test_partake_cross_user.py::test_partake_cross_user_unused_order_untouched |
| MP-15 | 权限/安全 | 越权退款/越权读取 | **暂不可测（后端未接入鉴权）** | — |
| MP-16 | 性能 | 阶梯加压 | **暂缓（JMeter/并发体系单列）** | — |

### 模块 4 · 账户额度 (activity/query_account_quota)

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MQ-01 | 等价类 | 有效 user+activity | 0000 + 六字段完整 | tests/test_account_quota.py::test_query_account_quota_returns_totals |
| MQ-02 | 等价类 | 不存在 user | ERR_BIZ_006 | tests/test_account_quota.py::test_query_account_quota_nonexistent_user_returns_error |
| MQ-03 | 等价类 | 不存在 activityId | ERR_BIZ_006 | testdata/readonly_cases.yaml::RO-QUOTA-002 |
| MQ-04 | 边界值 | userId 为空 | ERR_BIZ_006 | testdata/readonly_cases.yaml::RO-QUOTA-003 |
| MQ-05 | 边界值 | activityId=1 极小值 | ERR_BIZ_006 | testdata/readonly_cases.yaml::RO-QUOTA-005 |
| MQ-06 | 边界值 | activityId 负值 | ERR_BIZ_006 | testdata/readonly_cases.yaml::RO-QUOTA-004 |
| MQ-07 | 错误推测 | activityId 类型不匹配 | HTTP 400 | testdata/readonly_cases.yaml::RO-QUOTA-006 |

### 模块 5 · 中奖记录 (activity/query_user_award_record)

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MAW-01 | 等价类 | 有效 user+activity | 0000 | tests/test_award_record.py::test_query_user_award_record |
| MAW-02 | 等价类 | 有效 user+不存在的 activity | 0000 + 空列表（契约现状） | tests/test_award_record.py::test_query_user_award_record_invalid_activity_returns_empty |
| MAW-03 | 边界值 | 空 userId | 0000 + 空列表 | testdata/readonly_cases.yaml::RO-AWARD-003 |
| MAW-04 | 数据驱动 | 999999 极大值 | 0000 + 空列表 | testdata/readonly_cases.yaml::RO-AWARD-002 |

### 模块 6 · 协议层 / 数据结构

| ID | 方法 | 输入 | 预期 | 用例位置 |
|---|---|---|---|---|
| MH-01 | 错误推测 | 非法 JSON | HTTP 400 | tests/test_http_protocol.py::test_malformed_json_returns_400 |
| MH-02 | 错误推测 | GET 打 POST 接口 | HTTP 405 | tests/test_http_protocol.py::test_partake_post_only |
| MH-03 | 数据驱动 | readonly 矩阵 11 条 | 每条独立预期 | testdata/readonly_cases.yaml + tests/test_readonly_data_driven.py |

> 现状：**41 条已落地可运行**（42 条矩阵中的最后一条 MP-16 性能用例按项目范围外单独规划）。

### 错误推测

| 异常输入 | 预期 |
|---|---|
| activityId 不存在 | 非 `0000`（现状为 0001 泛错误码，已记录为待优化点） |
| userId 为空 / 超长 | `ERR_BIZ_006`（账户总额度不足） |
| JSON 非法 | HTTP 400 |
| GET 打 POST 接口 | HTTP 405 |

## 四、测试过程发现的真实缺陷（可作为简历/故障库素材）

| # | 现象 | 复现步骤 | 待办建议 |
|---|---|---|---|
| B1 | `strategy_armory` 传不存在的 strategyId 时接口长时间无响应（探测超时） | `GET /api/v1/raffle/strategy_armory?strategyId=999999` | 装配前先校验策略存在性并短路返回 |
| B2 | `raffle_activity.uq_strategy_id` 唯一约束：同一策略只能挂一个活动 | 插入第二个测试活动复用同一 strategy_id → `Duplicate entry` | 业务上是否合理需跟开发确认（通常一个策略服务多活动才合理）；测试数据也因此为每个测试活动各配一个占位策略号 |
| B3 | 无效 strategyId 查询奖池返回 `0000`+空列表，没有语义化错误码 | `POST /api/v1/raffle/query_raffle_award_list` body `{"strategyId":999999}` | 建议返回专用错误码 |
| B6 | 同一用户高并发首次参与抽奖：产生 **26 张** create 未使用订单 + 26 次额度扣减（预期各 1），竞态位置 `AbstractRaffleActivityPartake.createOrder` | 400 并发 15s，同一 userId；风暴前后 DB 核对（`docs/perf-report.md`） | 对 `(user_id, activity_id)` 做唯一性保护，或事务内 select for update / Redis 锁 |
| B7 | 并发 ≳200 时出现 HTTP 连接拒绝：写闭环 200 档 5 个、400 档 289 个 `HttpHostConnectException` | 阶梯压测；根因在 `application-dev.yml` Tomcat `threads.max=200` / `accept-count=10` | 调大 accept-count 与连接池上限，重走 400/800 阶梯验证 |
| B8 | 兜底奖品节点对空 `ruleValue` 抛裸 `NumberFormatException`：`RuleLuckAwardLogicTreeNode` 里 `if (split.length == 0)` 是死代码（`split` 永远至少返回 1 个元素，空串守卫永远不到） | `node.logic(userId, strategyId, awardId, "")` → `Integer.valueOf("")` 抛 NFE；用单测固化现状（`RuleLuckAwardLogicTreeNodeTest.luck_award_empty_config_throws_raw_number_format_exception`） | 修 guard 逻辑并换成业务异常 `AppException`，配置缺失应有明确错误码 |

## 三、数据准备

固定用户 `xiaofuge`（已有账户额度，用于幂等/一致性断言）。
场景法前先调用 `db.reset_partake_user("xiaofuge", 100301, 5)`，把总/日/月额度统一
重置为 5，保证每次执行都走“新建订单+扣额度”路径；用例结束后恢复快照，
避免历史数据漂移影响其他用例。
