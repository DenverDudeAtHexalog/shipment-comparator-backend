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

# --- Reference baseline (NOT live data) -------------------------------------------------------
# Published India West Coast -> US all-in ocean freight, per 40ft (Container News, July 2023).
# It is stale; it is only used so the simulated numbers sit in a plausible range for IN->US.
_REF_NOTE = ("Simulated estimate scaled from a published July 2023 India->US benchmark "
             "(40ft: ~USD 1,800 US East, ~1,900 US West, ~2,600 Gulf). Not a live market rate.")
_GENERIC_NOTE = "Generic placeholder estimate, not market data."
_EAST = {"USNYC", "USEWR", "USSAV", "USORF", "USBAL", "USCHS", "USBOS", "USMIA"}
_WEST = {"USLAX", "USLGB", "USOAK", "USSEA", "USTIW"}
_GULF = {"USHOU", "USMSY"}
_US_CITY_COAST = {"new york": 1800, "newark": 1800, "savannah": 1800, "norfolk": 1800, "baltimore": 1800,
                  "charleston": 1800, "boston": 1800, "miami": 1800,
                  "los angeles": 1900, "long beach": 1900, "oakland": 1900, "seattle": 1900, "tacoma": 1900,
                  "houston": 2600, "new orleans": 2600}


def _in_us_fcl_ref(shipment: ShipmentRequest) -> tuple[float, str] | None:
    """Per-40ft benchmark for India->US FCL, else None. Returns (usd_per_40ft, note)."""
    if shipment.mode != ShippingMode.SEA_FCL:
        return None
    if shipment.origin.country != "IN" or shipment.destination.country != "US":
        return None
    d = shipment.destination
    code = (d.port_code or "").upper()
    city = (d.city or "").lower()
    if code in _EAST:
        return 1800.0, _REF_NOTE
    if code in _WEST:
        return 1900.0, _REF_NOTE
    if code in _GULF:
        return 2600.0, _REF_NOTE
    if city in _US_CITY_COAST:
        return float(_US_CITY_COAST[city]), _REF_NOTE
    return 2100.0, _REF_NOTE + " Destination coast unknown, so an average was used."


def _fcl_base(shipment: ShipmentRequest, generic_base: float, vendor_mult: float, salt: str) -> tuple[float, str]:
    """Base freight for FCL and the note explaining its basis."""
    ref = _in_us_fcl_ref(shipment)
    if ref is None:
        return generic_base * _container_units(shipment) * _route_factor(shipment, salt), _GENERIC_NOTE
    per40, note = ref
    narrow = 0.95 + (int(hashlib.sha256(f"{salt}|n".encode()).hexdigest(), 16) % 11) / 100  # 0.95-1.05
    return per40 * _container_units(shipment) * vendor_mult * narrow, note


def _quote(provider: str, shipment: ShipmentRequest, service: str, base: float, days: tuple[int, int],
           fuel_pct: float = 0.0, extra: tuple[str, float] | None = None, note: str = _GENERIC_NOTE) -> Quote:
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
        transit_days_min=days[0], transit_days_max=days[1], charges=charges, notes=note, is_simulated=True, source="mock",
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
            base, note = _fcl_base(shipment, 1800, 1.00, "alpha")
            return [_quote(self.name, shipment, "Standard", base, (20, 28), fuel_pct=0.08, note=note)]
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
            base, note = _fcl_base(shipment, 1550, 0.93, "delta")
            return [_quote(self.name, shipment, "Ocean Saver", base, (24, 32), fuel_pct=0.05, note=note)]
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
            base, note = _fcl_base(shipment, 1700, 0.97, "foxtrot")
            fee = 45.0 * shipment.container_count
            return [_quote(self.name, shipment, "Standard", base, (21, 30), extra=("Port handling", round(fee, 2)), note=note)]
        return [_quote(self.name, shipment, "Standard", base, days, extra=("Port handling", round(fee, 2)))]


class SimVendor(BaseProvider):
    """Table-driven simulated forwarder that serves ALL modes. Same formulas as the others, different levels.

    air_rate: USD per chargeable kg; lcl_rate: USD per CBM; fcl_base / fcl_mult: generic and IN->US benchmark scaling.
    """

    def __init__(self, name: str, salt: str, air_rate: float, lcl_rate: float, fcl_base: float, fcl_mult: float,
                 air_days: tuple[int, int], lcl_days: tuple[int, int], fcl_days: tuple[int, int],
                 fuel_pct: float, delay: float, service: str = "Standard"):
        self.name = name
        self.salt, self.air_rate, self.lcl_rate = salt, air_rate, lcl_rate
        self.fcl_base, self.fcl_mult = fcl_base, fcl_mult
        self.air_days, self.lcl_days, self.fcl_days = air_days, lcl_days, fcl_days
        self.fuel_pct, self.delay, self.service = fuel_pct, delay, service

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(self.delay)
        f = _route_factor(shipment, self.salt)
        if shipment.mode == ShippingMode.AIR:
            return [_quote(self.name, shipment, self.service, _chargeable_weight_kg(shipment) * self.air_rate * f,
                           self.air_days, fuel_pct=self.fuel_pct)]
        if shipment.mode == ShippingMode.SEA_LCL:
            return [_quote(self.name, shipment, self.service, _cbm(shipment) * self.lcl_rate * f,
                           self.lcl_days, fuel_pct=self.fuel_pct)]
        base, note = _fcl_base(shipment, self.fcl_base, self.fcl_mult, self.salt)
        return [_quote(self.name, shipment, self.service, base, self.fcl_days, fuel_pct=self.fuel_pct, note=note)]


def extra_sim_vendors() -> list[SimVendor]:
    """More simulated vendors that serve every mode, so comparisons always have several priced rows."""
    return [
        SimVendor("SimLine Hotel (simulated)", "hotel", 4.0, 90, 1750, 0.96, (3, 5), (19, 26), (21, 29), 0.07, 0.35),
        SimVendor("SimTrans India (simulated)", "india", 3.8, 84, 1600, 0.90, (4, 7), (21, 29), (23, 31), 0.06, 0.45,
                  "Economy"),
        SimVendor("SimPort Juliet (simulated)", "juliet", 4.4, 97, 1850, 1.03, (2, 4), (17, 24), (19, 26), 0.09, 0.55,
                  "Priority"),
        SimVendor("SimCargo Kilo (simulated)", "kilo", 4.1, 89, 1680, 0.94, (3, 6), (20, 27), (22, 30), 0.05, 0.65),
        SimVendor("SimWorld Lima (simulated)", "lima", 3.6, 80, 1520, 0.89, (5, 8), (23, 31), (25, 34), 0.04, 0.75,
                  "Saver"),
        SimVendor("SimFreight Mike (simulated)", "mike", 4.6, 101, 1900, 1.06, (2, 3), (16, 23), (18, 25), 0.10, 0.5,
                  "Express"),
    ]


class SimLogixGamma(BaseProvider):
    """Always fails. Exists to demonstrate that one broken provider doesn't break the response."""
    name = "SimLogix Gamma (simulated outage)"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        await asyncio.sleep(0.2)
        raise ProviderError("Simulated provider outage (HTTP 503)")
