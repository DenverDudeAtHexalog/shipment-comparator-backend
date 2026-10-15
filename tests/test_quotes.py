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


def test_quotes_endpoint_only_priced_vendors_in_results():
    body = client.post("/api/v1/quotes", json=AIR).json()
    assert body["results"], "expected several priced vendors"
    assert all(x["status"] == "ok" and x["quotes"] for x in body["results"])
    assert len(body["results"]) >= 9
    assert body["contains_simulated"] is True
    assert all(q["is_simulated"] for x in body["results"] for q in x["quotes"])
    prices = [q["total_price"] for x in body["results"] for q in x["quotes"]]
    assert body["cheapest"]["total_price"] == min(prices)
    assert body["fastest"] is not None
    # unobtainable-price popular platforms appear as request boxes, not as prices
    boxes = {b["provider"] for b in body["request_quotes"]}
    assert {"Xhipment", "Cogoport", "Freightos"} <= boxes
    assert all(b["action_url"] for b in body["request_quotes"])
    # outage demo vendor is off by default
    assert body["unavailable"] == [] and not any("Gamma" in x["provider"] for x in body["results"])


def test_vendor_that_cannot_serve_is_hidden_everywhere():
    body = client.post("/api/v1/quotes", json={**AIR, "mode": "sea_fcl", "dimensions": None}).json()
    assert not any("Beta" in x["provider"] for x in body["results"])  # Beta has no FCL
    assert not any("Echo" in x["provider"] for x in body["results"])  # Echo is air only
    assert body["unavailable"] == [] and len(body["results"]) >= 8


def test_in_us_fcl_uses_labelled_reference_and_gulf_costs_more():
    base = {"origin": {"country": "IN", "port_code": "INNSA"}, "mode": "sea_fcl", "weight_kg": 18000,
            "container_type": "40HC"}

    def alpha(dest):
        body = client.post("/api/v1/quotes", json={**base, "destination": dest}).json()
        return next(q for x in body["results"] if "Alpha" in x["provider"] for q in x["quotes"])

    ny = alpha({"country": "US", "port_code": "USNYC"})
    hou = alpha({"country": "US", "port_code": "USHOU"})
    assert hou["total_price"] > ny["total_price"]
    assert "2023" in ny["notes"] and ny["is_simulated"]
    other = alpha({"country": "AE", "port_code": "AEJEA"})
    assert "not market data" in other["notes"]


def test_container_count_scales_fcl_price():
    one = {"origin": {"country": "IN", "port_code": "INNSA"}, "destination": {"country": "US", "port_code": "USLAX"},
           "mode": "sea_fcl", "weight_kg": 18000, "container_type": "40HC", "container_count": 1}
    two = {**one, "container_count": 2}

    def alpha(j):
        b = client.post("/api/v1/quotes", json=j).json()
        return next(q for x in b["results"] if "Alpha" in x["provider"] for q in x["quotes"])["total_price"]

    assert alpha(two) == pytest.approx(2 * alpha(one), rel=0.01)


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
    assert res.results == []
    assert [u.status.value for u in res.unavailable] == ["timeout", "error"]
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
