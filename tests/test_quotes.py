import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import BaseProvider
from app.schemas import Quote, ShipmentRequest, ShippingMode
from app.services.comparison import compare_quotes

client = TestClient(app)

AIR = {
    "origin": {"country": "IN", "city": "Chennai"},
    "destination": {"country": "AE", "city": "Dubai"},
    "mode": "air",
    "weight_kg": 120,
    "dimensions": {"length_cm": 50, "width_cm": 40, "height_cm": 30},
}


def test_quotes_endpoint_resilient_and_labelled():
    r = client.post("/api/v1/quotes", json=AIR)
    assert r.status_code == 200
    body = r.json()
    statuses = {x["provider"]: x["status"] for x in body["results"]}
    assert "error" in statuses.values() and "ok" in statuses.values()  # one failed, others fine
    assert body["contains_simulated"] is True
    assert all(q["is_simulated"] for x in body["results"] for q in x["quotes"])
    assert body["cheapest"] is not None and body["fastest"] is not None
    prices = [q["total_price"] for x in body["results"] for q in x["quotes"]]
    assert body["cheapest"]["total_price"] == min(prices)


def test_fcl_gives_no_quote_for_beta():
    body = client.post("/api/v1/quotes", json={**AIR, "mode": "sea_fcl", "dimensions": None}).json()
    beta = next(x for x in body["results"] if "Beta" in x["provider"])
    assert beta["status"] == "no_quote"


def test_invalid_input_422():
    assert client.post("/api/v1/quotes", json={**AIR, "weight_kg": 0}).status_code == 422


class _Slow(BaseProvider):
    name = "Slow"

    async def get_quotes(self, shipment):
        await asyncio.sleep(2)
        return []


class _Buggy(BaseProvider):
    name = "Buggy"

    async def get_quotes(self, shipment):
        raise KeyError("boom")


class _Mixed(BaseProvider):
    name = "Mixed"

    async def get_quotes(self, shipment):
        return [Quote(provider="Mixed", mode=ShippingMode.AIR, total_price=10, currency="EUR", source="test")]


@pytest.mark.asyncio
async def test_timeout_and_unexpected_exception():
    ship = ShipmentRequest(**AIR)
    res = await compare_quotes(ship, [_Slow(), _Buggy()], timeout=0.2)
    assert [r.status.value for r in res.results] == ["timeout", "error"]
    assert res.cheapest is None


@pytest.mark.asyncio
async def test_mixed_currencies_not_compared():
    class _RealUsd(BaseProvider):
        name = "RealUsd"

        async def get_quotes(self, shipment):
            return [Quote(provider="RealUsd", mode=ShippingMode.AIR, total_price=10, currency="USD", source="manual")]

    ship = ShipmentRequest(**AIR)
    res = await compare_quotes(ship, [_RealUsd(), _Mixed()])  # two REAL quotes: USD and EUR
    assert res.cheapest is None and "different currencies" in res.comparison_note
