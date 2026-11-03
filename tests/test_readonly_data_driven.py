"""只读接口的数据驱动用例：一个测试函数吃一整张 YAML 矩阵。"""

import pytest

from common.http_client import HttpClient
from common.yaml_loader import assert_expectation, load_cases


@pytest.mark.parametrize(
    "case",
    load_cases("readonly_cases.yaml"),
    ids=[case["id"] for case in load_cases("readonly_cases.yaml")],
)
def test_readonly_endpoint_case(api: HttpClient, case: dict):
    resp = api.request(case["endpoint"], case["payload"])
    assert_expectation(resp, case["expect"], case["id"])
