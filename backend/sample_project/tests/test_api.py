def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_list_products(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_product(client):
    response = client.get("/api/products/2")
    assert response.status_code == 200
    assert response.json()["name"] == "USB-C Hub"


def test_missing_product_returns_404(client):
    assert client.get("/api/products/999").status_code == 404


def test_create_order(client):
    response = client.post("/api/orders", json={"product_id": 1, "quantity": 2, "discount_code": "WELCOME10"})
    assert response.status_code == 201
    body = response.json()
    assert body["total_cents"] == 16020
    assert body["shipping_cents"] == 680


def test_get_order(client, created_order):
    response = client.get(f"/api/orders/{created_order['id']}")
    assert response.status_code == 200
    assert response.json()["quantity"] == 2


def test_order_validation(client):
    assert client.post("/api/orders", json={"product_id": 1, "quantity": 0}).status_code == 422


def test_shipping_quote(client):
    response = client.get("/api/shipping/quote", params={"weight_grams": 1000})
    assert response.status_code == 200
    assert response.json()["price_cents"] == 600
