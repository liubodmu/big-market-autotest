from common.http_client import HttpClient


def test_partake_post_only(api: HttpClient):
    resp = api.raw_request("activity/partake", method="GET")
    assert resp.status_code == 405


def test_malformed_json_returns_400(api: HttpClient):
    resp = api.raw_request(
        "activity/partake",
        method="POST",
        data="{bad json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
