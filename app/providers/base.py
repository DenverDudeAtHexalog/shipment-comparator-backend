"""Contract every logistics provider must follow.

To add a provider: subclass BaseProvider, implement get_quotes(), register it in
app/providers/registry.py. Nothing else in the app needs to change.
"""
from abc import ABC, abstractmethod

from app.schemas import Quote, ShipmentRequest


class ProviderError(Exception):
    """Provider failed (HTTP error, bad response, site changed...). Message is shown in the API response."""


class NoQuoteAvailable(Exception):
    """Provider worked fine but cannot serve this shipment (unsupported route/mode)."""


class QuotePending(Exception):
    """No instant price exists: the quote is delivered later (email / provider's app)."""

    def __init__(self, message: str, action_url: str | None = None):
        super().__init__(message)
        self.message = message
        self.action_url = action_url


class ProviderNotConfigured(Exception):
    """Integration exists but credentials (e.g. an API key) are missing."""


class BaseProvider(ABC):
    name: str  # human-readable provider name shown to users

    @abstractmethod
    async def get_quotes(self, shipment: ShipmentRequest) -> list[Quote]:
        """Return quotes, or raise NoQuoteAvailable / QuotePending / ProviderNotConfigured / ProviderError."""
