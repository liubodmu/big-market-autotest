import pymysql

from common.config import DB_CONFIG, DB_SCHEMAS


class DbClient:
    """读写客户端，用于接口返回结果与落库数据的比对、测试数据工厂与还原。

    db-router 会把 userId 分到 big_market_01 或 big_market_02，
    测试断言不依赖路由结果，所以默认同时操作两个分库。
    显式传入含 database 的 config（如 master 库）时，只操作这一个库。
    """

    def __init__(self, config: dict | None = None):
        passed = dict(config or DB_CONFIG)
        if "database" in passed and passed.get("database") != DB_CONFIG.get("database"):
            self._configs = [passed]
        else:
            self._configs = [dict(passed, database=s) for s in DB_SCHEMAS]

    def _each_config(self):
        for cfg in self._configs:
            yield cfg

    def _connect(self, cfg: dict):
        return pymysql.connect(
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            **cfg,
        )

    # ---------- 通用查询 ----------

    def query_one(self, sql: str, params: tuple = ()):
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    row = cursor.fetchone()
            if row is not None:
                return row
        return None

    def query_all(self, sql: str, params: tuple = ()):
        merged = []
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    for row in cursor.fetchall():
                        merged.append(dict(row, _db=cfg["database"]))
        return merged

    def execute(self, sql: str, params: tuple = ()) -> int:
        total = 0
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    total += cursor.execute(sql, params)
        return total

    def _sharded_tables(self, prefix: str) -> list[str]:
        found: list[str] = []
        for cfg in self._each_config():
            rows = self.query_all(
                "select table_name as tbl from information_schema.tables "
                "where table_schema = %s and table_name like %s",
                (cfg["database"], f"{prefix}\\_%"),
            )
            for row in rows:
                if row["tbl"] not in found:
                    found.append(row["tbl"])
        return found

    # ---------- 断言辅助 ----------

    def get_account_quota(self, user_id: str, activity_id: int):
        """读取三层账户额度。

        两个分库都被测试数据工厂种了相同的行，而应用只会更新其中一个
        分库，所以这里取“剩余额度最小的那一行”，即应用实际写入的分库。
        只有一个分库有行时直接返回该行。
        """
        rows = []
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "select total_count, total_count_surplus, day_count, day_count_surplus, "
                        "month_count, month_count_surplus "
                        "from raffle_activity_account where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    row = cursor.fetchone()
            if row is not None:
                rows.append(dict(row, _db=cfg["database"]))

        if not rows:
            return None
        return min(rows, key=lambda r: r.get("total_count_surplus", 0))

    def find_order_row(self, order_id: str):
        for table in self._sharded_tables("user_raffle_order"):
            for cfg in self._each_config():
                with self._connect(cfg) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"select order_id, user_id, activity_id, order_state "
                            f"from {table} where order_id = %s",
                            (order_id,),
                        )
                        row = cursor.fetchone()
                if row is not None:
                    return dict(row, _db=cfg["database"])
        return None

    def find_unused_order(self, user_id: str, activity_id: int):
        for table in self._sharded_tables("user_raffle_order"):
            for cfg in self._each_config():
                with self._connect(cfg) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"select order_id from {table} "
                            "where user_id = %s and activity_id = %s and order_state = 'create'",
                            (user_id, activity_id),
                        )
                        row = cursor.fetchone()
                if row is not None:
                    return dict(row, _db=cfg["database"])
        return None

    def mark_order_used(self, order_id: str) -> bool:
        for table in self._sharded_tables("user_raffle_order"):
            for cfg in self._each_config():
                with self._connect(cfg) as conn:
                    with conn.cursor() as cursor:
                        affected = cursor.execute(
                            f"update {table} set order_state = 'used' "
                            "where order_id = %s and order_state = 'create'",
                            (order_id,),
                        )
                if affected:
                    return True
        return False

    # ---------- 测试数据工厂 ----------

    def snapshot_user(self, user_id: str, activity_id: int) -> dict:
        mains = []
        month_rows = []
        day_rows = []
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "select total_count, total_count_surplus, day_count, day_count_surplus, "
                        "month_count, month_count_surplus "
                        "from raffle_activity_account where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    main = cursor.fetchone()
                    if main is not None:
                        mains.append(main)
                    cursor.execute(
                        "select month, month_count, month_count_surplus "
                        "from raffle_activity_account_month where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    month_rows.extend(cursor.fetchall())
                    cursor.execute(
                        "select day, day_count, day_count_surplus "
                        "from raffle_activity_account_day where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    day_rows.extend(cursor.fetchall())
        return {"main": mains[0] if mains else None,
                "month_rows": month_rows, "day_rows": day_rows}

    def reset_partake_user(self, user_id: str, activity_id: int, counts: int):
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    for table in self._sharded_tables("user_raffle_order"):
                        cursor.execute(
                            f"delete from {table} where user_id = %s and activity_id = %s",
                            (user_id, activity_id),
                        )
                    cursor.execute(
                        "delete from raffle_activity_account_month "
                        "where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    cursor.execute(
                        "delete from raffle_activity_account_day "
                        "where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    cursor.execute(
                        "insert into raffle_activity_account "
                        "(user_id, activity_id, total_count, total_count_surplus, "
                        "day_count, day_count_surplus, month_count, month_count_surplus) "
                        "values (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "on duplicate key update "
                        "total_count = values(total_count), "
                        "total_count_surplus = values(total_count_surplus), "
                        "day_count = values(day_count), "
                        "day_count_surplus = values(day_count_surplus), "
                        "month_count = values(month_count), "
                        "month_count_surplus = values(month_count_surplus)",
                        (user_id, activity_id, counts, counts, counts, counts, counts, counts),
                    )

    def restore_user(self, user_id: str, activity_id: int, snapshot: dict | None):
        self._wipe_quota_rows(user_id, activity_id)
        if snapshot is None:
            return

        main = snapshot.get("main")
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    # 用 upsert 而不是 insert，避免多库快照合并后撞唯一键
                    if main is not None:
                        cursor.execute(
                            "insert into raffle_activity_account "
                            "(user_id, activity_id, total_count, total_count_surplus, "
                            "day_count, day_count_surplus, month_count, month_count_surplus) "
                            "values (%s, %s, %s, %s, %s, %s, %s, %s) "
                            "on duplicate key update "
                            "total_count = values(total_count), total_count_surplus = values(total_count_surplus), "
                            "day_count = values(day_count), day_count_surplus = values(day_count_surplus), "
                            "month_count = values(month_count), month_count_surplus = values(month_count_surplus)",
                            (user_id, activity_id,
                             main["total_count"], main["total_count_surplus"],
                             main["day_count"], main["day_count_surplus"],
                             main["month_count"], main["month_count_surplus"]),
                        )
                    for row in snapshot.get("month_rows") or []:
                        cursor.execute(
                            "insert into raffle_activity_account_month "
                            "(user_id, activity_id, month, month_count, month_count_surplus) "
                            "values (%s, %s, %s, %s, %s) on duplicate key update "
                            "month_count = values(month_count), "
                            "month_count_surplus = values(month_count_surplus)",
                            (user_id, activity_id, row["month"], row["month_count"], row["month_count_surplus"]),
                        )
                    for row in snapshot.get("day_rows") or []:
                        cursor.execute(
                            "insert into raffle_activity_account_day "
                            "(user_id, activity_id, day, day_count, day_count_surplus) "
                            "values (%s, %s, %s, %s, %s) on duplicate key update "
                            "day_count = values(day_count), day_count_surplus = values(day_count_surplus)",
                            (user_id, activity_id, row["day"], row["day_count"], row["day_count_surplus"]),
                        )

    def _wipe_quota_rows(self, user_id: str, activity_id: int):
        for cfg in self._each_config():
            with self._connect(cfg) as conn:
                with conn.cursor() as cursor:
                    for table in self._sharded_tables("user_raffle_order"):
                        cursor.execute(
                            f"delete from {table} where user_id = %s and activity_id = %s",
                            (user_id, activity_id),
                        )
                    cursor.execute(
                        "delete from raffle_activity_account where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    cursor.execute(
                        "delete from raffle_activity_account_month where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )
                    cursor.execute(
                        "delete from raffle_activity_account_day where user_id = %s and activity_id = %s",
                        (user_id, activity_id),
                    )

    def seed_account_month(self, user_id: str, activity_id: int, month: str,
                           month_count_surplus: int):
        self.execute(
            "insert into raffle_activity_account_month "
            "(user_id, activity_id, month, month_count, month_count_surplus) "
            "values (%s, %s, %s, %s, %s) on duplicate key update "
            "month_count = values(month_count), month_count_surplus = values(month_count_surplus)",
            (user_id, activity_id, month, month_count_surplus, month_count_surplus),
        )

    def seed_account_day(self, user_id: str, activity_id: int, day: str,
                         day_count_surplus: int):
        self.execute(
            "insert into raffle_activity_account_day (user_id, activity_id, day, day_count, "
            "day_count_surplus) values (%s, %s, %s, %s, %s) on duplicate key update "
            "day_count = values(day_count), day_count_surplus = values(day_count_surplus)",
            (user_id, activity_id, day, day_count_surplus, day_count_surplus),
        )

    # ---------- 活动元数据（master 库） ----------

    def get_activity(self, activity_id: int):
        return self.query_one(
            "select activity_id, state, begin_date_time, end_date_time "
            "from raffle_activity where activity_id = %s",
            (activity_id,),
        )

    def insert_test_activity(self, activity_id: int, activity_name: str, state: str,
                             begin_date_time: str, end_date_time: str,
                             strategy_id: int = 100006):
        return self.query_one(
            "insert into raffle_activity "
            "(activity_id, activity_name, activity_desc, begin_date_time, end_date_time, "
            "strategy_id, state, create_time, update_time) "
            "values (%s, %s, %s, %s, %s, %s, %s, now(), now())",
            (activity_id, activity_name, activity_name,
             begin_date_time, end_date_time, strategy_id, state),
        )

    def delete_test_activity(self, activity_id: int):
        return self.execute(
            "delete from raffle_activity where activity_id = %s",
            (activity_id,),
        )

    def restore_quota(self, user_id: str, activity_id: int, snapshot: dict):
        self.restore_user(user_id, activity_id, snapshot)
