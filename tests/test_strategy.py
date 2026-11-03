from common.http_client import HttpClient


STRATEGY_ID = 100006


def test_strategy_armory_success(api: HttpClient):
    resp = api.request("raffle/strategy_armory", params={"strategyId": STRATEGY_ID}, method="GET")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000"
    assert body["data"] is True


def test_query_raffle_award_list_structure(api: HttpClient):
    payload = {"strategyId": STRATEGY_ID}
    resp = api.request("raffle/query_raffle_award_list", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000"
    award_pool = body["data"]
    assert isinstance(award_pool, list)
    assert len(award_pool) > 0
    for award in award_pool:
        assert award["awardId"] > 0
        assert award["awardTitle"]
        assert award["sort"] > 0


def test_query_raffle_award_list_invalid_strategy_returns_empty(api: HttpClient):
    payload = {"strategyId": 999999}
    resp = api.request("raffle/query_raffle_award_list", payload)

    assert resp.status_code == 200
    body = resp.json()
    # 现状：无效策略返回成功码 + 空列表（属可优化点，已记录到故障库）
    assert body["code"] == "0000"
    assert body["data"] == []


def test_random_raffle_award_in_strategy_pool(api: HttpClient):
    armory = api.request("raffle/strategy_armory", params={"strategyId": STRATEGY_ID}, method="GET")
    assert armory.status_code == 200
    assert armory.json()["code"] == "0000"

    pool_resp = api.request("raffle/query_raffle_award_list", {"strategyId": STRATEGY_ID})
    award_pool = pool_resp.json()["data"]
    assert award_pool

    for _ in range(3):
        resp = api.request("raffle/random_raffle", {"strategyId": STRATEGY_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0000"
        data = body["data"]
        matching = [a for a in award_pool if a["awardId"] == data["awardId"]]
        assert matching, f"抽奖结果 {data['awardId']} 应在奖池内"
        assert data["awardIndex"] == matching[0]["sort"]


def test_random_raffle_invalid_strategy_returns_error(api: HttpClient):
    payload = {"strategyId": 999999}
    resp = api.request("raffle/random_raffle", payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0001", f"不存在的策略抽奖应返回 0001，实际 {body}"


def test_random_raffle_missing_body_returns_illegal_parameter(api: HttpClient):
    resp = api.request("raffle/random_raffle", {})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0002", f"缺 strategyId 应返回 0002，实际 {body}"


def test_query_raffle_award_list_missing_payload_returns_empty(api: HttpClient):
    resp = api.request("raffle/query_raffle_award_list", {})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0000", f"缺 body 应返回 0000，实际 {body}"
    assert body["data"] == [], f"缺 body 应返回空列表，实际 {body}"
