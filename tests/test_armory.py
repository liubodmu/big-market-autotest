"""策略装配接口的幂等性测试。"""

from common.http_client import HttpClient


STRATEGY_ID = 100006


def test_strategy_armory_idempotent(api: HttpClient):
    first = api.request("raffle/strategy_armory", params={"strategyId": STRATEGY_ID}, method="GET")
    second = api.request("raffle/strategy_armory", params={"strategyId": STRATEGY_ID}, method="GET")

    for label, resp in (("first", first), ("second", second)):
        assert resp.status_code == 200, f"{label} armory HTTP 应 200，实际 {resp.status_code}"
        body = resp.json()
        assert body["code"] == "0000", f"{label} armory 应 0000，实际 {body}"
        assert body["data"] is True, f"{label} armory data 应为 True，实际 {body}"


def test_strategy_armory_does_not_mutate_award_pool(api: HttpClient):
    before = api.request("raffle/query_raffle_award_list", {"strategyId": STRATEGY_ID}).json()["data"]
    api.request("raffle/strategy_armory", params={"strategyId": STRATEGY_ID}, method="GET")
    after = api.request("raffle/query_raffle_award_list", {"strategyId": STRATEGY_ID}).json()["data"]

    assert {a["awardId"] for a in before} == {a["awardId"] for a in after}, (
        f"armory 装配不应改变奖池。before={before} after={after}"
    )
