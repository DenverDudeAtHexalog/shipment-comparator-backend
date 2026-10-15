import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.providers.manual import ManualQuoteProvider
from app.providers.pending import request_only_providers
from app.providers.searates import SearatesProvider
from app.schemas import ProviderStatus, Quote, ShipmentRequest, ShippingMode
from app.services.comparison import build_comparison, compare_quotes

client = TestClient(app)

FCL_IN_US = {
    "origin": {"country": "IN", "port_code": "INNSA"},
    "destination": {"country": "US", "port_code": "USLAX"},
    "mode": "sea_fcl",
    "weight_kg": 18000,
    "container_type": "40HC",
}


def _ship(**over) -> ShipmentRequest:
    return ShipmentRequest(**{**FCL_IN_US, **over})


def _manual_file(tmp_path, **over):
    entry = {"provider": "Test Forwarder", "origin_country": "IN", "destination_country": "US",
             "mode": "sea_fcl", "container_type": "40HC", "total_price": 2500, "currency": "usd",
             "transit_days_min": 30, "transit_days_max": 35, "display_permitted": True,
             "valid_until": (date.today() + timedelta(days=5)).isoformat()}
    entry.update(over)
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"quotes": [entry]}))
    return p


def test_intoglo_box_only_for_in_us_fcl():
    res = client.post("/api/v1/quotes", json=FCL_IN_US).json()
    box = next(x for x in res["request_quotes"] if x["provider"] == "Intoglo")
    assert box["action_url"]
    air = {**FCL_IN_US, "mode": "air", "dimensions": {"length_cm": 50, "width_cm": 40, "height_cm": 30}}
    body = client.post("/api/v1/quotes", json=air).json()
    assert not any(x["provider"] == "Intoglo" for x in body["request_quotes"])
    assert body["unavailable"] == []


def test_request_boxes_and_searates_hidden():
    res = client.post("/api/v1/quotes", json=FCL_IN_US).json()
    boxes = {x["provider"] for x in res["request_quotes"]}
    assert {"Intoglo", "Xhipment", "Cogoport", "Freightos", "FreightMango", "Agraga", "Flexport"} == boxes
    assert res["unavailable"] == []  # hidden by default
    assert not any(x["provider"] in boxes for x in res["results"])


async def test_manual_quote_used_only_when_permitted(tmp_path):
    ok = await compare_quotes(_ship(), [ManualQuoteProvider(_manual_file(tmp_path))])
    q = ok.results[0].quotes[0]
    assert q.source == "manual" and q.is_simulated is False and q.currency == "USD"
    blocked = await compare_quotes(_ship(), [ManualQuoteProvider(_manual_file(tmp_path, display_permitted=False))])
    assert blocked.results == [] and blocked.unavailable[0].status == ProviderStatus.NO_QUOTE


async def test_manual_quote_expired_or_wrong_lane_skipped(tmp_path):
    expired = _manual_file(tmp_path, valid_until=(date.today() - timedelta(days=1)).isoformat())
    assert (await compare_quotes(_ship(), [ManualQuoteProvider(expired)])).unavailable[0].status == ProviderStatus.NO_QUOTE
    wrong = _manual_file(tmp_path, destination_country="AE")
    assert (await compare_quotes(_ship(), [ManualQuoteProvider(wrong)])).unavailable[0].status == ProviderStatus.NO_QUOTE


async def test_missing_or_corrupt_manual_file(tmp_path):
    assert (await compare_quotes(_ship(), [ManualQuoteProvider(tmp_path / "nope.json")])).unavailable[0].status == ProviderStatus.NO_QUOTE
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert (await compare_quotes(_ship(), [ManualQuoteProvider(bad)])).unavailable[0].status == ProviderStatus.ERROR


async def test_providers_dont_crash_and_pending_has_no_price():
    res = await compare_quotes(_ship(), [*request_only_providers(), SearatesProvider()])
    assert res.results == [] and res.cheapest is None and res.fastest is None
    assert len(res.request_quotes) == 7
    assert [u.provider for u in res.unavailable] == ["SeaRates"]


def test_real_quotes_beat_simulated_in_ranking():
    def q(price, sim):
        return Quote(provider="p", mode=ShippingMode.SEA_FCL, total_price=price, currency="USD",
                     transit_days_max=20, is_simulated=sim, source="mock" if sim else "manual")
    from app.schemas import ProviderResult
    results = [ProviderResult(provider="Sim", status="ok", quotes=[q(100, True)]),
               ProviderResult(provider="Real", status="ok", quotes=[q(2500, False)])]
    out = build_comparison(_ship(), results)
    assert out.cheapest.total_price == 2500 and out.cheapest.is_simulated is False
    assert out.contains_simulated is True and "simulated quotes are excluded" in out.comparison_note


def _ok_vendors(body):
    return [r["provider"] for r in client.post("/api/v1/quotes", json=body).json()["results"]
            if r["status"] == "ok" and r["quotes"]]


def test_every_mode_gets_several_vendors():
    lcl = {**FCL_IN_US, "mode": "sea_lcl", "dimensions": {"length_cm": 100, "width_cm": 100, "height_cm": 100}}
    air = {**FCL_IN_US, "mode": "air", "weight_kg": 200,
           "dimensions": {"length_cm": 50, "width_cm": 40, "height_cm": 30}}
    for body in (FCL_IN_US, lcl, air):
        assert len(_ok_vendors(body)) >= 3, body["mode"]


def test_fcl_price_scales_with_container_count_and_type():
    async def alpha(**over):
        from app.providers.mock import SimFreightAlpha
        res = await compare_quotes(_ship(**over), [SimFreightAlpha()])
        return res.results[0].quotes[0].total_price
    import asyncio
    one = asyncio.run(alpha())
    assert abs(asyncio.run(alpha(container_count=2)) - 2 * one) < 0.05
    assert asyncio.run(alpha(container_type="20RF")) > asyncio.run(alpha(container_type="20GP"))


def test_multi_service_vendor_returns_two_quotes():
    air = {**FCL_IN_US, "mode": "air", "weight_kg": 200,
           "dimensions": {"length_cm": 50, "width_cm": 40, "height_cm": 30}}
    res = client.post("/api/v1/quotes", json=air).json()["results"]
    echo = next(r for r in res if "Echo" in r["provider"])
    assert len(echo["quotes"]) == 2
