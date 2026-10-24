def test_health(client) -> None:
    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
