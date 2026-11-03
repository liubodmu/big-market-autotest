# 性能测试脚本

## 前置

- 被测服务在 `127.0.0.1:8091`（本地运行）
- MySQL `127.0.0.1:13306`、Redis `127.0.0.1:16379` 可用
- JMeter 5.6.3 CLI（本机解压在 `F:\big-market\tools\apache-jmeter-5.6.3`）

## 步骤

1. 造压测用户池（写闭环每次请求消耗一个尚未扣减过额度的用户）：

   ```bash
   python performance/seed_load_users.py   # 默认 30000 人，100 万额度，写 load_users.csv
   ```

2. 只读阶梯（query_account_quota，无副作用）：

   ```bash
   jmeter.bat -n -t performance/plans/read_ladder.jmx  -l performance/results/read_50.jtl  -Jthreads=50  -Jrampup=5  -Jduration=60
   # 重复 100/200/400，输出 read_100/200/400.jtl
   ```

3. 写闭环阶梯（partake，CSV 顺序消费唯一用户）：

   ```bash
   jmeter.bat -n -t performance/plans/write_ladder.jmx -l performance/results/write_50.jtl -Jthreads=50 -Jrampup=3 -Jduration=30
   ```

4. 同用户并发风暴（partake + 同一 userId，验证锁/复制冲突）：

   ```bash
   jmeter.bat -n -t performance/plans/storm_plan.jmx     -l performance/results/storm_400.jtl -Jthreads=400 -Jrampup=2 -Jduration=15
   ```

5. 解析 JTL：

   ```bash
   python performance/parse_jtl.py performance/results/*.jtl
   ```

6. 收尾清理压测用户（写闭环后按需）：

   ```bash
   python performance/seed_load_users.py --clean
   ```
