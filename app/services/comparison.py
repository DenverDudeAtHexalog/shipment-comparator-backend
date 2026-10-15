"""Runs all providers concurrently and builds the comparison. Never raises because of a provider."""
import asyncio
import time

from app.config import PROVIDER_TIMEOUT_SECONDS
from app.providers.base import (
    BaseProvider,
    NoQuoteAvailable,
    ProviderError,
    ProviderNotConfigured,
    QuotePending,
)
from app.schemas import (
    ProviderResult,
    ProviderStatus,
    Quote,
    QuoteResponse,
    RequestBox,
    ShipmentRequest,
    UnavailableProvider,
)


async def _run_provider(provider: BaseProvider, shipment: ShipmentRequest, timeout: float) -> ProviderResult:
    start = time.perf_counter()

    def elapsed() -> int:
        return int((time.perf_counter() - start) * 1000)

    def result(status: ProviderStatus, **kw) -> ProviderResult:
        return ProviderResult(provider=provider.name, status=status, elapsed_ms=elapsed(), **kw)

    try:
        quotes = await asyncio.wait_for(provider.get_quotes(shipment), timeout=timeout)
        quotes = [q for q in quotes if q.total_price > 0]  # drop missing/zero prices
        if not quotes:
            return result(ProviderStatus.NO_QUOTE, error="Provider returned no priced quotes")
        return result(ProviderStatus.OK, quotes=quotes)
    except NoQuoteAvailable as e:
        return result(ProviderStatus.NO_QUOTE, message=str(e))
    except QuotePending as e:
        return result(ProviderStatus.PENDING, message=e.message, action_url=e.action_url)
    except ProviderNotConfigured as e:
        return result(ProviderStatus.NOT_CONFIGURED, message=str(e))
    except asyncio.TimeoutError:
        return result(ProviderStatus.TIMEOUT, error=f"No response within {timeout:g}s")
    except ProviderError as e:
        return result(ProviderStatus.ERROR, error=str(e))
    except Exception as e:  # a buggy provider must never crash the request
        return result(ProviderStatus.ERROR, error=f"Unexpected error: {type(e).__name__}")


def _transit_key(q: Quote) -> int | None:
    return q.transit_days_max if q.transit_days_max is not None else q.transit_days_min


def build_comparison(shipment: ShipmentRequest, all_results: list[ProviderResult]) -> QuoteResponse:
    results = [r for r in all_results if r.status == ProviderStatus.OK and r.quotes]
    request_quotes = [
        RequestBox(provider=r.provider, message=r.message or "No automatic price available.", action_url=r.action_url)
        for r in all_results if r.status == ProviderStatus.PENDING
    ]
    unavailable = [
        UnavailableProvider(provider=r.provider, status=r.status, reason=r.message or r.error)
        for r in all_results
        if r.status not in (ProviderStatus.OK, ProviderStatus.PENDING) or (r.status == ProviderStatus.OK and not r.quotes)
    ]
    quotes = [q for r in results for q in r.quotes]
    notes: list[str] = []
    cheapest = fastest = None

    # Never rank fake prices against real ones: if any real quote exists, compare real quotes only.
    real = [q for q in quotes if not q.is_simulated]
    pool = real if real else quotes
    if real and len(real) != len(quotes):
        notes.append("Cheapest/fastest use real quotes only; simulated quotes are excluded.")

    if pool:
        currencies = {q.currency for q in pool}
        if len(currencies) == 1:
            cheapest = min(pool, key=lambda q: q.total_price)
        else:
            notes.append(f"Quotes are in different currencies ({', '.join(sorted(currencies))}); cheapest not computed.")
        with_transit = [q for q in pool if _transit_key(q) is not None]
        if with_transit:
            fastest = min(with_transit, key=lambda q: (_transit_key(q), q.total_price))

    return QuoteResponse(
        request=shipment, results=results, request_quotes=request_quotes, unavailable=unavailable,
        cheapest=cheapest, fastest=fastest,
        contains_simulated=any(q.is_simulated for q in quotes),
        comparison_note=" ".join(notes) or None,
    )


async def compare_quotes(shipment: ShipmentRequest, providers: list[BaseProvider],
                         timeout: float = PROVIDER_TIMEOUT_SECONDS) -> QuoteResponse:
    results = await asyncio.gather(*(_run_provider(p, shipment, timeout) for p in providers))
    return build_comparison(shipment, list(results))
