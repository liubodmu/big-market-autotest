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

## 三、数据准备

固定用户 `xiaofuge`（已有账户额度，用于幂等/一致性断言）。
场景法前先调用 `db.reset_partake_user("xiaofuge", 100301, 5)`，把总/日/月额度统一
重置为 5，保证每次执行都走“新建订单+扣额度”路径；用例结束后恢复快照，
避免历史数据漂移影响其他用例。
