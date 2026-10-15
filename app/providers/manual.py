"""Real quotes your team received (email, phone, provider app) and is ALLOWED to display.

Stored in data/manual_quotes.json (git-ignored). See data/manual_quotes.example.json for the format.
Safeguards:
- an entry is only used when "display_permitted" is true (provider terms may forbid sharing quotes);
- expired entries (valid_until in the past) are skipped;
- results carry source="manual" and is_simulated=false, so they are never confused with mock data.
"""
import json
from datetime import date
from pathlib import Path

from app.config import MANUAL_QUOTES_FILE
from app.providers.base import BaseProvider, NoQuoteAvailable, ProviderError
from app.schemas import Quote, ShipmentRequest, ShippingMode


class ManualQuoteProvider(BaseProvider):
    name = "Manually entered quotes"

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else MANUAL_QUOTES_FILE

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        if not self.path.exists():
            raise NoQuoteAvailable("No manual quotes file found")
        try:
            entries = json.loads(self.path.read_text(encoding="utf-8")).get("quotes", [])
        except (OSError, ValueError, AttributeError) as e:
            raise ProviderError(f"Could not read manual quotes file: {type(e).__name__}") from e

        quotes: list[Quote] = []
        for e in entries:
            try:
                if not e.get("display_permitted", False):
                    continue
                if e["origin_country"].upper() != shipment.origin.country:
                    continue
                if e["destination_country"].upper() != shipment.destination.country:
                    continue
                if ShippingMode(e["mode"]) != shipment.mode:
                    continue
                ctype = e.get("container_type")
                if ctype and shipment.container_type and ctype != shipment.container_type.value:
                    continue
                valid_until = date.fromisoformat(e["valid_until"]) if e.get("valid_until") else None
                if valid_until and valid_until < date.today():
                    continue
                quotes.append(Quote(
                    provider=e["provider"], mode=shipment.mode, service_name=e.get("service_name"),
                    total_price=float(e["total_price"]), currency=e["currency"].upper(),
                    transit_days_min=e.get("transit_days_min"), transit_days_max=e.get("transit_days_max"),
                    valid_until=valid_until,
                    notes=e.get("notes") or f"Entered manually from a quote received {e.get('received_on', 'earlier')}",
                    is_simulated=False, source="manual",
                ))
            except (KeyError, ValueError, TypeError):
                continue  # skip malformed entries instead of failing the whole provider
        if not quotes:
            raise NoQuoteAvailable("No permitted, unexpired manual quote for this lane")
        return quotes
