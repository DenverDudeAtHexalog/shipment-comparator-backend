"""Platforms we can NOT fetch a price from automatically. We say so honestly instead of inventing a number.

The UI shows each of these as a box: "no automatic price - request it there" with a link.
Facts below come from each platform's public pages / public write-ups (checked 15 Oct 2026):
- Intoglo: its "Get Instant Quote" form (India -> USA, FCL) saves a lead and shows "Expect your
  personalised quote in your inbox". No price on screen, no public API found.
- Xhipment: quotes are "shared ... on the digital platform" (login). No public API found. Its Quotation
  Terms restrict reproducing/distributing quotes without written consent.
- FreightMango, Agraga, Flexport: listed because they are widely used; no price API verified.
- Cogoport, Freightos: described publicly as offering instant online quotes; no public price API verified.
- Only the most widely used platforms are listed; the rest are dropped rather than shown as clutter.
Do not POST to any site's internal endpoints from the backend: that only creates sales leads.
"""
from collections.abc import Callable

from app.providers.base import BaseProvider, NoQuoteAvailable, QuotePending
from app.schemas import Quote, ShipmentRequest, ShippingMode


class RequestOnlyProvider(BaseProvider):
    def __init__(self, name: str, url: str, message: str,
                 lane: Callable[[ShipmentRequest], bool] | None = None, lane_error: str = ""):
        self.name = name
        self.url = url
        self.message = message
        self.lane = lane
        self.lane_error = lane_error

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        if self.lane and not self.lane(shipment):
            raise NoQuoteAvailable(self.lane_error)
        raise QuotePending(self.message, action_url=self.url)


def _generic(facts: str) -> str:
    return f"{facts} We can't fetch its price automatically yet, so open it to get a quote."


def _in_us_fcl(s: ShipmentRequest) -> bool:
    return s.mode == ShippingMode.SEA_FCL and s.origin.country == "IN" and s.destination.country == "US"


def request_only_providers() -> list[RequestOnlyProvider]:
    return [
        RequestOnlyProvider(
            "Intoglo", "https://www.intoglo.com/instant-quote/fcl",
            "Intoglo emails a personalised quote after you submit its form; no price is available instantly.",
            lane=_in_us_fcl, lane_error="Intoglo's quote form only covers India to USA full-container (FCL) shipments",
        ),
        RequestOnlyProvider(
            "Xhipment", "https://app.xhipment.com",
            "Xhipment shares quotes on its digital platform (account required). Its quotation terms restrict "
            "sharing quotes without written consent, so none are shown here.",
        ),
        RequestOnlyProvider(
            "Cogoport", "https://www.cogoport.com",
            _generic("Cogoport offers instant container quotes through its rate-discovery tool."),
        ),
        RequestOnlyProvider(
            "Freightos", "https://www.freightos.com",
            _generic("Freightos compares air, ocean and trucking quotes from many providers."),
        ),
        RequestOnlyProvider(
            "FreightMango", "https://www.freightmango.com",
            _generic("FreightMango is a digital freight marketplace."),
        ),
        RequestOnlyProvider(
            "Agraga", "https://www.agraga.com",
            _generic("Agraga is an India-based platform for cross-border logistics for MSMEs."),
        ),
        RequestOnlyProvider(
            "Flexport", "https://www.flexport.com",
            "Flexport has no public instant quote; its public site routes enquiries to an expert. "
            "Request a quote from them directly.",
        ),
    ]
