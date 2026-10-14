import os

import httpx
import pytest

os.environ.setdefault("SHIPPING_API_URL", "http://shipping.mock.local")


def _shipping_handler(request: httpx.Request) -> httpx.Response:
    weight = int(request.url.params.get("weight", "0"))
    return httpx.Response(200, json={"price_cents": 500 + weight // 10})


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Disposable SQLite database + local mock shipping API for every test."""
    from shoplite.clients import shipping

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(shipping, "TRANSPORT", httpx.MockTransport(_shipping_handler))
    yield


@pytest.fixture
def client(isolated_env):
    from fastapi.testclient import TestClient

    from shoplite.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def created_order(client):
    response = client.post("/api/orders", json={"product_id": 1, "quantity": 2})
    assert response.status_code == 201
    return response.json()
