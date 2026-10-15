"""The single place where providers are switched on/off."""
from app import config
from app.providers.base import BaseProvider
from app.providers.manual import ManualQuoteProvider
from app.providers.mock import (
    SimAirEcho,
    SimCargoBeta,
    SimFreightAlpha,
    SimGlobalFoxtrot,
    SimLogixGamma,
    SimOceanDelta,
)
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
        providers += [  # SIMULATED demo data: several vendors per mode so comparisons have something to compare
            SimFreightAlpha(), SimCargoBeta(), SimOceanDelta(), SimAirEcho(), SimGlobalFoxtrot(),
            SimLogixGamma(),  # always fails, on purpose
        ]
    return providers
