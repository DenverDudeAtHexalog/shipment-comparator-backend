"""SIMULATED providers for development and demo. Prices here are NOT real.

Every Quote they return has is_simulated=True and source="mock". The formulas are simple on purpose:
they react to weight, volume, container type/count and route so the demo looks sensible,
but they say nothing about real market rates.
"""
import asyncio
import hashlib

from app.providers.base import BaseProvider, NoQuoteAvailable, ProviderError
from app.schemas import Charge, ContainerType, Quote, ShipmentRequest, ShippingMode

# Relative cost of one container by type (40HC = 1.0). Simulated.
_CONTAINER_FACTOR = {
    ContainerType.GP_20: 0.6,
    ContainerType.HC_40: 1.0,
    ContainerType.RF_20: 1.5,
    ContainerType.RF_40: 2.2,
}


def _route_factor(shipment: ShipmentRequest, salt: str) -> float:
    """Deterministic 0.85-1.15 multiplier per route so results are stable between calls."""
    key = f"{salt}|{shipment.origin.country}|{shipment.destination.country}".encode()
    return 0.85 + (int(hashlib.sha256(key).hexdigest(), 16) % 31) / 100


def _chargeable_weight_kg(shipment: ShipmentRequest) -> float:
    """Air: greater of actual weight and volumetric weight (CBM x 167)."""
    if shipment.dimensions:
        volumetric = shipment.dimensions.volume_cbm * 167 * shipment.package_count
        return max(shipment.weight_kg, volumetric)
    return shipment.weight_kg


def _cbm(shipment: ShipmentRequest) -> float:
    return max(shipment.dimensions.volume_cbm * shipment.package_count, 1.0)  # 1 CBM minimum


def _container_units(shipment: ShipmentRequest) -> float:
    """Number of containers weighted by type, e.g. 2 x 20GP = 1.2 units. Defaults to 40HC."""
    ctype = shipment.container_type or ContainerType.HC_40
    return shipment.container_count * _CONTAINER_FACTOR[ctype]


def _quote(provider: str, shipment: ShipmentRequest, service: str, base: float, days: tuple[int, int],
           fuel_pct: float = 0.0, extra: tuple[str, float] | None = None) -> Quote:
    charges = [Charge(name="Base freight", amount=round(base, 2))]
    total = base
    if fuel_pct:
        fuel = round(base * fuel_pct, 2)
        charges.append(Charge(name="Fuel surcharge", amount=fuel))
        total += fuel
    if extra:
        charges.append(Charge(name=extra[0], amount=extra[1]))
        total += extra[1]
    return Quote(
        provider=provider, mode=shipment.mode, service_name=service, total_price=round(total, 2), currency="USD",
        transit_days_min=days[0], transit_days_max=days[1], charges=charges, is_simulated=True, source="mock",
    )


class SimFreightAlpha(BaseProvider):
    """All modes, mid price."""
    name = "SimFreight Alpha (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.3)  # pretend network latency
        f = _route_factor(shipment, "alpha")
        if shipment.mode == ShippingMode.AIR:
            base, days = _chargeable_weight_kg(shipment) * 4.2 * f, (3, 5)
        elif shipment.mode == ShippingMode.SEA_LCL:
            base, days = _cbm(shipment) * 95 * f, (18, 25)
        else:
            base, days = 1800 * _container_units(shipment) * f, (20, 28)
        return [_quote(self.name, shipment, "Standard", base, days, fuel_pct=0.08)]


class SimCargoBeta(BaseProvider):
    """Cheaper but slower. Air and LCL only (no full-container service)."""
    name = "SimCargo Beta (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.6)
        if shipment.mode == ShippingMode.SEA_FCL:
            raise NoQuoteAvailable("Beta does not offer full-container shipments")
        f = _route_factor(shipment, "beta")
        if shipment.mode == ShippingMode.AIR:
            base, days = _chargeable_weight_kg(shipment) * 3.7 * f, (5, 8)
        else:
            base, days = _cbm(shipment) * 82 * f, (22, 30)
        return [_quote(self.name, shipment, "Economy", base, days)]


class SimOceanDelta(BaseProvider):
    """Sea only (FCL and LCL). Cheap FCL, slow."""
    name = "SimOcean Delta (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.4)
        if shipment.mode == ShippingMode.AIR:
            raise NoQuoteAvailable("Delta only offers sea freight")
        f = _route_factor(shipment, "delta")
        if shipment.mode == ShippingMode.SEA_LCL:
            base, days = _cbm(shipment) * 88 * f, (21, 28)
        else:
            base, days = 1550 * _container_units(shipment) * f, (24, 32)
        return [_quote(self.name, shipment, "Ocean Saver", base, days, fuel_pct=0.05)]


class SimAirEcho(BaseProvider):
    """Air only, two service levels (so one provider can return several quotes)."""
    name = "SimAir Echo (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.5)
        if shipment.mode != ShippingMode.AIR:
            raise NoQuoteAvailable("Echo only offers air freight")
        f = _route_factor(shipment, "echo")
        w = _chargeable_weight_kg(shipment)
        return [
            _quote(self.name, shipment, "Express", w * 5.1 * f, (2, 3), fuel_pct=0.12),
            _quote(self.name, shipment, "Deferred", w * 3.9 * f, (4, 6), fuel_pct=0.12),
        ]


class SimGlobalFoxtrot(BaseProvider):
    """All modes, flat port-handling fee, slightly slower than Alpha."""
    name = "SimGlobal Foxtrot (simulated)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.7)
        f = _route_factor(shipment, "foxtrot")
        if shipment.mode == ShippingMode.AIR:
            base, days, fee = _chargeable_weight_kg(shipment) * 4.5 * f, (3, 6), 25.0
        elif shipment.mode == ShippingMode.SEA_LCL:
            base, days, fee = _cbm(shipment) * 91 * f, (19, 27), 45.0
        else:
            base, days, fee = 1700 * _container_units(shipment) * f, (21, 30), 45.0 * shipment.container_count
        return [_quote(self.name, shipment, "Standard", base, days, extra=("Port handling", round(fee, 2)))]


class SimLogixGamma(BaseProvider):
    """Always fails. Exists to demonstrate that one broken provider doesn't break the response."""
    name = "SimLogix Gamma (simulated outage)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.2)
        raise ProviderError("Simulated provider outage (HTTP 503)")
