"""解析 JMeter JTL（csv 格式），输出每档压测的吞吐/延迟/错误统计。"""

import argparse
import csv
import statistics


def percentile(sorted_values, percent):
    if not sorted_values:
        return 0
    index = int(round((len(sorted_values) - 1) * percent / 100))
    return sorted_values[index]


def parse_one(path):
    samples = 0
    failures = 0
    latency = []
    codes = {}
    timestamps = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            samples += 1
            latency.append(int(row["elapsed"]))
            timestamps.append(int(row["timeStamp"]))
            code = row["responseCode"]
            codes[code] = codes.get(code, 0) + 1
            if row["success"].strip().lower() != "true":
                failures += 1

    if not samples:
        return None

    start = min(timestamps)
    end = max(timestamps) + max(latency)
    seconds = max((end - start) / 1000.0, 0.001)
    latency.sort()
    return {
        "samples": samples,
        "throughput": round(samples / seconds, 1),
        "min": min(latency),
        "avg": round(statistics.mean(latency), 1),
        "p50": percentile(latency, 50),
        "p90": percentile(latency, 90),
        "p95": percentile(latency, 95),
        "p99": percentile(latency, 99),
        "max": max(latency),
        "error_rate": round(failures * 100.0 / samples, 2),
        "codes": codes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    for path in args.files:
        result = parse_one(path)
        if result is None:
            print(f"{path}: EMPTY")
            continue
        print(f"{path}: {result}")


if __name__ == "__main__":
    main()
