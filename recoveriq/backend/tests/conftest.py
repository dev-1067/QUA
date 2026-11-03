import os
import shutil
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="riq-test-")
os.environ["RIQ_DATA_DIR"] = _tmp
os.environ["DEMO_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_tmp, ignore_errors=True)


def login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo@1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@recoveriq.in")


@pytest.fixture(scope="session")
def agent(client):
    return login(client, "agent@recoveriq.in")


@pytest.fixture(scope="session")
def l2(client):
    return login(client, "l2.mumbai@recoveriq.in")


@pytest.fixture(scope="session")
def execu(client):
    return login(client, "exec@recoveriq.in")
