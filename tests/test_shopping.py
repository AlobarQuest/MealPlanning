def test_shopping_page(authed_client):
    resp = authed_client.get("/shopping")
    assert resp.status_code == 200
    assert "start_date" in resp.text
    assert "end_date" in resp.text


def test_shopping_generate_empty(authed_client):
    resp = authed_client.post("/shopping/generate", data={
        "start_date": "2026-02-23",
        "end_date": "2026-03-01",
        "use_pantry": "on",
    })
    assert resp.status_code == 200


def test_shopping_generate_no_pantry(authed_client):
    resp = authed_client.post("/shopping/generate", data={
        "start_date": "2026-02-23",
        "end_date": "2026-03-01",
    })
    assert resp.status_code == 200


def test_shopping_export(authed_client):
    resp = authed_client.post("/shopping/export", data={
        "start_date": "2026-02-23",
        "end_date": "2026-03-01",
        "use_pantry": "on",
    })
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
