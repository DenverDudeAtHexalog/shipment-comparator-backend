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
    extra_sim_vendors,
)
from app.providers.pending import request_only_providers
from app.providers.searates import SearatesProvider


def get_providers() -> list[BaseProvider]:
    providers: list[BaseProvider] = [
        ManualQuoteProvider(),     # real quotes your team entered and may display
        SearatesProvider(),        # hidden until SEARATES_API_KEY is set and the mapping is built
        *request_only_providers(),  # popular platforms: shown as "request a quote there" boxes
    ]
    if config.ENABLE_MOCK_PROVIDERS:
        providers += [  # SIMULATED demo data: several vendors per mode
            SimFreightAlpha(), SimCargoBeta(), SimOceanDelta(), SimAirEcho(), SimGlobalFoxtrot(),
            *extra_sim_vendors(),
        ]
    if config.ENABLE_OUTAGE_DEMO:
        providers.append(SimLogixGamma())  # always fails, on purpose
    return providers
