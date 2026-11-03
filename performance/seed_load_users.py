"""压测用户池造数/清理。

用法：
  python performance/seed_load_users.py            # 默认 30000 人，每人 100 万额度
  python performance/seed_load_users.py --count 30000 --quota 1000000
  python performance/seed_load_users.py --clean

同时在 big_market_01 / big_market_02 两个分库插入同一批主账户额度行，
保证压测流量无论被 db-router 路到哪个库都能命中账户。
"""

import argparse
from pathlib import Path

import pymysql

SHARDS = ["big_market_01", "big_market_02"]
ORDER_TABLES = [f"user_raffle_order_{i:03d}" for i in range(4)]


def chunked(seq, size):
    for index in range(0, len(seq), size):
        yield seq[index:index + size]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=30000)
    parser.add_argument("--prefix", default="load_user_")
    parser.add_argument("--activity", type=int, default=100301)
    parser.add_argument("--quota", type=int, default=1000000)
    parser.add_argument("--batch", type=int, default=1000)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    user_ids = [f"{args.prefix}{index:05d}" for index in range(1, args.count + 1)]
    connection = pymysql.connect(host="127.0.0.1", port=13306, user="root",
                                 password="123456", charset="utf8mb4", autocommit=True)
    cursor = connection.cursor()

    if args.clean:
        for shard in SHARDS:
            cursor.execute(
                f"delete from {shard}.raffle_activity_account where user_id like '{args.prefix}%%'")
            cursor.execute(
                f"delete from {shard}.raffle_activity_account_month where user_id like '{args.prefix}%%'")
            cursor.execute(
                f"delete from {shard}.raffle_activity_account_day where user_id like '{args.prefix}%%'")
            for table in ORDER_TABLES:
                cursor.execute(
                    f"delete from {shard}.{table} where user_id like '{args.prefix}%%'")
        print("cleaned load users")
        return

    seed_sql = (
        "insert into {shard}.raffle_activity_account "
        "(user_id, activity_id, total_count, total_count_surplus, "
        "day_count, day_count_surplus, month_count, month_count_surplus) "
        "values {rows} "
        "on duplicate key update total_count = values(total_count), "
        "total_count_surplus = values(total_count_surplus), day_count = values(day_count), "
        "day_count_surplus = values(day_count_surplus), month_count = values(month_count), "
        "month_count_surplus = values(month_count_surplus)"
    )
    row = "(%s, %s, %s, %s, %s, %s, %s, %s)"
    for shard in SHARDS:
        cursor.execute(f"delete from {shard}.raffle_activity_account_month where user_id like '{args.prefix}%%'")
        cursor.execute(f"delete from {shard}.raffle_activity_account_day where user_id like '{args.prefix}%%'")
        for table in ORDER_TABLES:
            cursor.execute(f"delete from {shard}.{table} where user_id like '{args.prefix}%%'")
        for batch in chunked(user_ids, args.batch):
            rows = ", ".join([row] * len(batch))
            params = []
            for user_id in batch:
                params.extend([user_id, args.activity, args.quota, args.quota,
                               args.quota, args.quota, args.quota, args.quota])
            cursor.execute(seed_sql.format(shard=shard, rows=rows), tuple(params))
        print(f"seeded {len(user_ids)} users into {shard}")

    csv_path = Path(__file__).parent / "load_users.csv"
    csv_path.write_text("\n".join(user_ids) + "\n", encoding="utf-8")
    print(f"csv written: {csv_path}")


if __name__ == "__main__":
    main()
