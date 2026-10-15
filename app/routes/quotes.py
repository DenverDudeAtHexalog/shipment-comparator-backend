from fastapi import APIRouter

from app import config

from app.providers.registry import get_providers
from app.schemas import QuoteResponse, ShipmentRequest
from app.services.comparison import compare_quotes

router = APIRouter(prefix="/api/v1", tags=["quotes"])


@router.post("/quotes", response_model=QuoteResponse)
async def get_quotes(shipment: ShipmentRequest) -> QuoteResponse:
    """Ask every registered provider for a quote and return a comparison."""
    response = await compare_quotes(shipment, get_providers())
    if not config.SHOW_UNAVAILABLE:
        response.unavailable = []  # vendors that can't serve this shipment are simply not shown
    return response


@router.get("/providers")
async def list_providers():
    return {"providers": [p.name for p in get_providers()]}


@router.post("/shipments/validate")
async def validate_shipment(shipment: ShipmentRequest):
    """Check a request body without calling any provider."""
    return {"valid": True, "shipment": shipment}
