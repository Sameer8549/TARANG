"""Weather router — live coastal conditions."""

from fastapi import APIRouter
from services.weather_service import get_weather

router = APIRouter()


@router.get("", summary="Get weather for coordinates")
async def weather(lat: float = 12.8698, lng: float = 74.8431):
    """Fetch live weather / marine conditions for given lat/lng."""
    return await get_weather(lat, lng)
