"""Shared data models (request + response). Every provider and the frontend speak these."""
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ShippingMode(str, Enum):
    AIR = "air"
    SEA_FCL = "sea_fcl"  # full container
    SEA_LCL = "sea_lcl"  # shared container


class CargoType(str, Enum):
    GENERAL = "general"
    FRAGILE = "fragile"
    PERISHABLE = "perishable"
    HAZARDOUS = "hazardous"
    ELECTRONICS = "electronics"


class ContainerType(str, Enum):
    GP_20 = "20GP"
    HC_40 = "40HC"
    RF_20 = "20RF"  # refrigerated
    RF_40 = "40RF"


class Location(BaseModel):
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2, e.g. IN")
    city: str | None = Field(None, examples=["Chennai"])
    port_code: str | None = Field(None, description="UN/LOCODE, e.g. INMAA", examples=["INMAA"])

    @model_validator(mode="after")
    def _need_city_or_port(self):
        self.country = self.country.upper()
        if not (self.city or self.port_code):
            raise ValueError("Provide at least a city or a port_code")
        return self


class Dimensions(BaseModel):
    length_cm: float = Field(..., gt=0)
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)

    @property
    def volume_cbm(self) -> float:
        return self.length_cm * self.width_cm * self.height_cm / 1_000_000


class ShipmentRequest(BaseModel):
    origin: Location
    destination: Location
    mode: ShippingMode
    cargo_type: CargoType = CargoType.GENERAL
    weight_kg: float = Field(..., gt=0, le=1_000_000)
    dimensions: Dimensions | None = None
    package_count: int = Field(1, ge=1)
    ready_date: date | None = None
    # Full-container (sea_fcl) details
    container_type: ContainerType | None = None
    container_count: int = Field(1, ge=1, le=50)
    goods_description: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def _check_mode_rules(self):
        if self.mode in (ShippingMode.AIR, ShippingMode.SEA_LCL) and self.dimensions is None:
            raise ValueError(f"dimensions are required for mode '{self.mode.value}'")
        return self


class Charge(BaseModel):
    name: str  # e.g. "Fuel surcharge"
    amount: float


class Quote(BaseModel):
    provider: str
    mode: ShippingMode
    service_name: str | None = None  # provider's own label for the service
    total_price: float = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    transit_days_min: int | None = None
    transit_days_max: int | None = None
    charges: list[Charge] = []
    valid_until: date | None = None
    notes: str | None = None  # quote basis / exclusions the UI should show next to the price
    # Honesty flags: the frontend MUST show these.
    is_simulated: bool = False  # True = fake demo data, not a real price
    source: str = "unknown"  # "mock" | "api" | "manual" | "web_automation"


class ProviderStatus(str, Enum):
    OK = "ok"
    NO_QUOTE = "no_quote"  # provider replied but can't serve this route
    PENDING = "pending"  # quote must be requested; arrives later by email / in provider's app
    NOT_CONFIGURED = "not_configured"  # integration exists but needs credentials
    TIMEOUT = "timeout"
    ERROR = "error"


class ProviderResult(BaseModel):
    provider: str
    status: ProviderStatus
    quotes: list[Quote] = []
    error: str | None = None
    message: str | None = None  # human-readable explanation for non-ok statuses
    action_url: str | None = None  # where the user can request/see the quote
    elapsed_ms: int | None = None


class RequestBox(BaseModel):
    """A popular platform we can't fetch a price from. The UI shows a box: 'request this quote there'."""
    provider: str
    message: str
    action_url: str | None = None
    action_label: str = "Request quote"


class UnavailableProvider(BaseModel):
    """Providers that returned nothing useful (can't serve this lane, not configured, timed out...).
    The UI should NOT show these; they are kept for debugging and transparency."""
    provider: str
    status: ProviderStatus
    reason: str | None = None


class QuoteResponse(BaseModel):
    request: ShipmentRequest
    results: list[ProviderResult]  # ONLY providers that returned at least one priced quote
    request_quotes: list[RequestBox] = []  # popular platforms without an automatic price
    unavailable: list[UnavailableProvider] = []
    cheapest: Quote | None = None
    fastest: Quote | None = None
    contains_simulated: bool = False  # True if ANY quote is fake demo data
    comparison_note: str | None = None  # e.g. why cheapest could not be computed
