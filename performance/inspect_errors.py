"""汇总 JTL 里的失败样本，按 (HTTP 状态码 + 失败信息) 聚类。"""

import argparse
import csv
from collections import Counter


def inspect(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if row["success"].strip().lower() != "true"]
    clusters = Counter((row["responseCode"], row["failureMessage"]) for row in rows)
    print(f"===== {path} failed={len(rows)}")
    for (code, message), count in clusters.most_common():
        print(f"  {count:>6} {code} {message[:160]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    for path in args.files:
        inspect(path)


if __name__ == "__main__":
    main()
