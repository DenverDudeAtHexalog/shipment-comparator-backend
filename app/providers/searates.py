"""SeaRates (Logistics Explorer API) integration - READY FOR A KEY, NOT YET MAPPED.

What is verified: SeaRates advertises a REST rates API covering ocean FCL/LCL, air and land
(https://www.searates.com/reference/api-logistics-explorer/, https://docs.searates.com).
What is NOT verified: free tier / trial, how keys are issued, request parameters, response format.
So this class only checks for a key and then reports clearly that the mapping is still to do.
Once you have docs + a key: set SEARATES_API_KEY in .env, then implement _fetch() and _parse()
using httpx.AsyncClient, return Quote(..., source="api", is_simulated=False).
"""
from app.config import SEARATES_API_KEY
from app.providers.base import BaseProvider, ProviderError, ProviderNotConfigured
from app.schemas import Quote, ShipmentRequest


class SearatesProvider(BaseProvider):
    name = "SeaRates"

    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        if not SEARATES_API_KEY:
            raise ProviderNotConfigured("Set SEARATES_API_KEY in .env to enable SeaRates")
        raise ProviderError("SeaRates request/response mapping not implemented yet (needs the API docs)")
