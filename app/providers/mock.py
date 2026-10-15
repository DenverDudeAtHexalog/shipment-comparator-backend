"""SIMULATED providers for development and demo. Prices here are NOT real.

Every Quote they return has is_simulated=True and source="mock".
"""
import asyncio
import hashlib

from app.providers.base import BaseProvider, NoQuoteAvailable, ProviderError
from app.schemas import Charge, Quote, ShipmentRequest, ShippingMode


def _route_factor(shipment: ShipmentRequest, salt: str) -> float:
    """Deterministic 0.85-1.15 multiplier per route so results are stable between calls."""
    key = f"{salt}|{shipment.origin.country}|{shipment.destination.country}".encode()
    return 0.85 + (int(hashlib.sha256(key).hexdigest(), 16) % 31) / 100


def _chargeable_weight_kg(shipment: ShipmentRequest) -> float:
    if shipment.dimensions:
        volumetric = shipment.dimensions.volume_cbm * 167 * shipment.package_count  # air convention
        return max(shipment.weight_kg, volumetric)
    return shipment.weight_kg


class SimFreightAlpha(BaseProvider):
    name = "SimFreight Alpha (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.3)  # pretend network latency
        f = _route_factor(shipment, "alpha")
        if shipment.mode == ShippingMode.AIR:
            base = _chargeable_weight_kg(shipment) * 4.2 * f
            days = (3, 5)
        elif shipment.mode == ShippingMode.SEA_LCL:
            cbm = max(shipment.dimensions.volume_cbm * shipment.package_count, 1.0)
            base = cbm * 95 * f
            days = (18, 25)
        else:  # FCL
            base = 1800 * f
            days = (20, 28)
        fuel = round(base * 0.08, 2)
        base = round(base, 2)
        return [Quote(
            provider=self.name, mode=shipment.mode, service_name="Standard",
            total_price=round(base + fuel, 2), currency="USD",
            transit_days_min=days[0], transit_days_max=days[1],
            charges=[Charge(name="Base freight", amount=base), Charge(name="Fuel surcharge", amount=fuel)],
            is_simulated=True, source="mock",
        )]


class SimCargoBeta(BaseProvider):
    """Cheaper but slower. Does not offer full-container (FCL) service."""
    name = "SimCargo Beta (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.6)
        if shipment.mode == ShippingMode.SEA_FCL:
            raise NoQuoteAvailable("Beta does not offer full-container shipments")
        f = _route_factor(shipment, "beta")
        if shipment.mode == ShippingMode.AIR:
            total, days = _chargeable_weight_kg(shipment) * 3.7 * f, (5, 8)
        else:
            cbm = max(shipment.dimensions.volume_cbm * shipment.package_count, 1.0)
            total, days = cbm * 82 * f, (22, 30)
        return [Quote(
            provider=self.name, mode=shipment.mode, service_name="Economy",
            total_price=round(total, 2), currency="USD",
            transit_days_min=days[0], transit_days_max=days[1],
            is_simulated=True, source="mock",
        )]


class SimLogixGamma(BaseProvider):
    """Always fails. Exists to demonstrate that one broken provider doesn't break the response."""
    name = "SimLogix Gamma (simulated outage)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.2)
        raise ProviderError("Simulated provider outage (HTTP 503)")