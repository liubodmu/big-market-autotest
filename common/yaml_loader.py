"""YAML 数据驱动用例的统一加载器与断言器。

Case Betreff shape（缺一即报错，从源头把“半成品数据”挡住）：

    - id: <语义化编号，全表唯一>
      desc: <一句话>
      endpoint: <相对 API 前缀的 path>
      payload: <dict>
      expect:  <由 assert_expectation 解释的断言字典>
"""

from pathlib import Path

import yaml

TESTDATA_DIR = Path(__file__).resolve().parents[1] / "testdata"


def load_cases(filename: str) -> list[dict]:
    document = yaml.safe_load((TESTDATA_DIR / filename).read_text(encoding="utf-8"))
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{filename} 里没有 cases 列表")

    seen_ids = set()
    for case in cases:
        case_id = case.get("id")
        if not case_id:
            raise ValueError(f"每条用例都需要 id：{case}")
        if case_id in seen_ids:
            raise ValueError(f"重复的用例 id：{case_id}")
        seen_ids.add(case_id)
        for required in ("desc", "endpoint", "payload"):
            if required not in case:
                raise ValueError(f"用例 {case_id} 缺少 {required}")
    return cases


def assert_expectation(resp, expect: dict, case_id: str = "") -> None:
    """通用断言，把 expect dict 里的键组合成一组顺序断言。"""
    body = resp.json()
    label = f"[{case_id}] " if case_id else ""

    if "http_status" in expect:
        expected_status = expect["http_status"]
        assert resp.status_code == expected_status, (
            f"{label}HTTP 状态应为 {expected_status}，实际 {resp.status_code}"
        )

    if "code" in expect:
        expected_code = expect["code"]
        assert body.get("code") == expected_code, (
            f"{label}code 应为 {expected_code}，实际 {body.get('code')}"
        )

    if expect.get("code_not_success"):
        assert body.get("code") != "0000", f"{label}不应返回成功，实际 {body}"

    data = body.get("data")

    if "data_keys" in expect:
        for key in expect["data_keys"]:
            assert data is not None and key in data, f"{label}data 应包含 {key}，实际 {data}"

    if "data_numeric_nonneg" in expect:
        for key in expect["data_numeric_nonneg"]:
            value = (data or {}).get(key)
            assert isinstance(value, int) and value >= 0, (
                f"{label}{key} 应为非负整数，实际 {value}"
            )

    if "data_fields_equal" in expect:
        for key, expected_value in expect["data_fields_equal"].items():
            actual_value = (data or {}).get(key)
            assert actual_value == expected_value, (
                f"{label}data.{key} 应为 {expected_value}，实际 {actual_value}"
            )

    if expect.get("data_empty_list"):
        assert data == [], f"{label}data 应为空列表，实际 {data}"

    if "data_items_count_min" in expect:
        minimum = expect["data_items_count_min"]
        assert isinstance(data, list) and len(data) >= minimum, (
            f"{label}data 应至少 {minimum} 条，实际 {data}"
        )

    if "data_items_required" in expect:
        assert isinstance(data, list) and data, f"{label}data 应为非空列表，实际 {data}"
        for item in data:
            for required in expect["data_items_required"]:
                assert required in item, f"{label}data 元素缺少 {required}，实际 {item}"

    if "data_items_numeric_min" in expect:
        for field, minimum in expect["data_items_numeric_min"].items():
            for item in data if isinstance(data, list) else []:
                value = item.get(field)
                assert isinstance(value, int) and value >= minimum, (
                    f"{label}data.{field} 应 >= {minimum}，实际 {value}"
                )

    if "data_items_enum" in expect:
        for field, allowed in expect["data_items_enum"].items():
            for item in data if isinstance(data, list) else []:
                value = item.get(field)
                assert value in allowed, f"{label}data.{field} 应在 {allowed}，实际 {value}"

    if "data_items_nonempty" in expect:
        for field in expect["data_items_nonempty"]:
            for item in data if isinstance(data, list) else []:
                value = item.get(field)
                assert isinstance(value, str) and value, (
                    f"{label}data.{field} 应为非空字符串，实际 {value}"
                )
