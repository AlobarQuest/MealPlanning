import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_env(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    demo_file = tmp_path_factory.mktemp("demo") / "demo.db"
    os.environ["DB_PATH"] = str(db_file)
    os.environ["APP_PASSWORD"] = "testpass"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
    os.environ["DEMO_DB_URL"] = str(demo_file)


@pytest.fixture(scope="session")
def client(set_test_env):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="session")
def authed_client(client):
    client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    return client
