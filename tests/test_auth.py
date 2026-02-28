def test_login_page_returns_200(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "password" in resp.text.lower()


def test_login_wrong_password_returns_error(client):
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()


def test_login_correct_password_redirects_and_sets_cookie(client):
    resp = client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/pantry"
    assert "mp_session" in resp.cookies


def test_protected_route_redirects_unauthenticated():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True, cookies={}) as fresh:
        fresh.cookies.clear()
        resp = fresh.get("/pantry", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_logout_clears_session():
    # Use an isolated client so logout doesn't pollute the session-scoped authed_client
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        c.post("/login", data={"password": "testpass"}, follow_redirects=False)
        resp = c.post("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "mp_session" in set_cookie
    assert "max-age=0" in set_cookie.lower()
