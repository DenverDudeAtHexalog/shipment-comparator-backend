"""Providers that do NOT give an instant price. We say so honestly instead of inventing one.

Findings (checked 15 Oct 2026, public pages only):
- Intoglo: its "Get Instant Quote" form (India -> USA, FCL) saves a lead and shows "Expect your
  personalised quote in your inbox". No price is returned on screen and no public API was found.
- Xhipment: quotes are "shared ... on the digital platform" (login at app.xhipment.com). No public API
  found. Its Quotation Terms restrict reproducing/distributing quotes without written consent.
Do not POST to either site's internal endpoints from the backend: that only creates sales leads.
"""
from app.providers.base import BaseProvider, NoQuoteAvailable, QuotePending
from app.schemas import Quote, ShipmentRequest, ShippingMode


class IntogloProvider(BaseProvider):
    name = "Intoglo"
    URL = "https://www.intoglo.com/instant-quote/fcl"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        lane_ok = (shipment.mode == ShippingMode.SEA_FCL
                   and shipment.origin.country == "IN" and shipment.destination.country == "US")
        if not lane_ok:
            raise NoQuoteAvailable("Intoglo's quote form only covers India to USA full-container (FCL) shipments")
        raise QuotePending(
            "Intoglo emails a personalised quote after you submit its form; no price is available instantly.",
            action_url=self.URL,
        )


class XhipmentProvider(BaseProvider):
    name = "Xhipment"
    URL = "https://app.xhipment.com"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        raise QuotePending(
            "Xhipment shares quotes on its digital platform (account required). Its quotation terms "
            "restrict sharing quotes without written consent, so none are shown here.",
            action_url=self.URL,
        )
