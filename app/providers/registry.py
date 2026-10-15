"""The single place where providers are switched on/off."""
from app import config
from app.providers.base import BaseProvider
from app.providers.manual import ManualQuoteProvider
from app.providers.mock import SimCargoBeta, SimFreightAlpha, SimLogixGamma
from app.providers.pending import IntogloProvider, XhipmentProvider
from app.providers.searates import SearatesProvider


def get_providers() -> list[BaseProvider]:
    providers: list[BaseProvider] = [
        ManualQuoteProvider(),  # real quotes your team entered and may display
        IntogloProvider(),      # pending: quote arrives by email
        XhipmentProvider(),     # pending: quote lives in their app
        SearatesProvider(),     # needs SEARATES_API_KEY + mapping
    ]
    if config.ENABLE_MOCK_PROVIDERS:
        providers += [SimFreightAlpha(), SimCargoBeta(), SimLogixGamma()]  # SIMULATED demo data
    return providers
