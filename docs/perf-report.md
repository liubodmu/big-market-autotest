# 性能测试报告

测试环境：Windows 本机（Spring Boot 8091 + MySQL 8.0 13306 + Redis 6.2 16379 + RabbitMQ 5672 同机部署）。
工具：JMeter 5.6.3 CLI（`-n` 模式），JTL 由 `performance/parse_jtl.py` 汇总，错误明细由 `performance/inspect_errors.py` 聚类。
口径：**本机基线**，绝对吞吐不代表生产水位；重点看增长趋势、饱和点与失败模式。

## 一、只读链路（POST query_account_quota，60s/档）

| 并发 | 采样数 | 吞吐 req/s | avg | p50 | p95 | p99 | max | 错误 |
|---|---|---|---|---|---|---|---|---|
| 50 | 23634 | 366.8 | 121.5 | 97 | 276 | 462 | 4704 | 0% |
| 100 | 30179 | 492.8 | 190.7 | 182 | 350 | 484 | 1383 | 0% |
| 200 | 29555 | 473.6 | 390.3 | 391 | 698 | 874 | 2562 | 0% |
| 400 | 31057 | 496.7 | 745.2 | 724 | 1182 | 1398 | 2602 | 0% |

**结论**：吞吐饱和点在 **100 并发（≈490 req/s）**，200/400 档吞吐不再增长，延迟随并发近似线性上升（p95 350ms→1182ms），业务侧 0 错误。只读瓶颈在应用线程池与连接池，不在 Redis/MySQL 本身。

## 二、写闭环（POST partake，30s/档，每请求消耗独立压测用户）

| 并发 | 采样数 | 吞吐 req/s | avg | p50 | p95 | p99 | max | 错误 |
|---|---|---|---|---|---|---|---|---|
| 50 | 2937 | 95.3 | 486.8 | 464 | 769 | 979 | 1131 | 0 |
| 100 | 5656 | 170.4 | 510.5 | 373 | 1339 | 2024 | 3522 | 0 |
| 200 | 7591 | 213.8 | 777.3 | 540 | 2305 | 3245 | 5751 | 5 连接拒绝 |
| 400 | 9458 | 262.0 | 1273.4 | 903 | 3471 | 4412 | 6274 | 0 |

**结论**：写闭环在 400 档吞吐 ~262 req/s，尾部延迟显著恶化（p95 3.4s），并在 200 档出现 5 个 `HttpHostConnectException` 连接拒绝——根因指向 `application-dev.yml` 中 Tomcat `threads.max=200` / `accept-count=10`（同口径风暴 400 档集中出现 289 个连接拒绝），外加每分库 Hikari `maximum-pool-size=25` 二级放大延迟。

## 三、并发正确性风暴（同 userId 400 并发 15s，storm_user 开户后）

风暴 HTTP 层稳定（5706 请求，0 HTTP 错误，~230.7 req/s），但**业务一致性被击穿**：

| 校验点 | 预期 | 实际 |
|---|---|---|
| 该 user 的 create 未使用订单数 | 1 | **26 张**（分布在 big_market_01.user_raffle_order_003） |
| 该 user 三层额度净扣减次数 | 1 | **26 次**（总/日/月都从 100 万扣到 999974） |

根因：`AbstractRaffleActivityPartake.createOrder` 里"查询未使用订单"和"落库新订单"之间不是原子操作，同一用户并发请求各自读到"无订单"各自插入。已记为缺陷 **B6**（`docs/test-design.md`）。修复建议：对 `(user_id, activity_id)` 增加唯一性保护（唯一索引 + 事务内占位），或事务内 `select ... for update`，或 Redis 分布式锁前置。

另注：**storm_user 未开户时**的那次风暴（storm_100/400 银 storm_400.jtl）HTTP 都是 200，业务码全是 `ERR_BIZ_006` —— JMeter 的 success 只校验 HTTP 200，**业务码必须在响应断言内单独校验**，这个教训已写进本题目的执行约束。

## 四、优化建议（按优先级）
1. **B6 并发写保护**（P0）：见上；修复后重跑同用户风暴，正确预期 “1 张订单 + 1 次扣减”。
2. **B7 接入层瓶颈**（P1）：`accept-count` 10 → 200/400，`threads.max` 200 → 400，重走 400/800 阶梯观察吞吐抬升。
3. **连接池扩大**（P2）：Hikari `maximum-pool-size=25/分库` 在 400 并发下拖长尾部，可扩 60-80 观察 p95/p99。

## 五、复现步骤

1. `python performance/seed_load_users.py` 造 30000 压测用户池 + `load_users.csv`
2. 按档起 JMeter CLI（`performance/README.md` 有完整命令），read/write/storm 三组各档跑数
3. `python performance/parse_jtl.py performance/results/*.jtl` 出数字
4. `python performance/inspect_errors.py performance/results/*.jtl` 出错误聚类
5. 风暴前后用 SQL 核对该 userId 的订单数与三层额度扣减一致性（报告第三节用的就是这套 SQL）
6. `python performance/seed_load_users.py --clean` / `--prefix storm_user --clean` 清理压测用户
