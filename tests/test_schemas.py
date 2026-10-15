from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

GOOD = {
    "origin": {"country": "in", "city": "Chennai", "port_code": "INMAA"},
    "destination": {"country": "AE", "city": "Dubai"},
    "mode": "air",
    "weight_kg": 120,
    "dimensions": {"length_cm": 50, "width_cm": 40, "height_cm": 30},
}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_valid_request_and_country_uppercased():
    r = client.post("/api/v1/shipments/validate", json=GOOD)
    assert r.status_code == 200
    assert r.json()["shipment"]["origin"]["country"] == "IN"


def test_air_requires_dimensions():
    bad = {k: v for k, v in GOOD.items() if k != "dimensions"}
    assert client.post("/api/v1/shipments/validate", json=bad).status_code == 422


def test_negative_weight_rejected():
    assert client.post("/api/v1/shipments/validate", json={**GOOD, "weight_kg": -5}).status_code == 422


def test_location_needs_city_or_port():
    bad = {**GOOD, "destination": {"country": "AE"}}
    assert client.post("/api/v1/shipments/validate", json=bad).status_code == 422