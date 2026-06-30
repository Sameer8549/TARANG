"""
AI Triage route — direct triage endpoint for testing / manual re-triage.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from services.ai_triage import run_triage
from services.weather_service import get_weather

router = APIRouter()


class ManualTriageRequest(BaseModel):
    alert_id:    str = "TEST-001"
    vessel_id:   str = "VES-001"
    vessel_name: str = "Test Vessel"
    lat:         float = 12.889
    lng:         float = 74.842
    alert_type:  str = "sos_manual"
    use_weather: bool = True


@router.post("", summary="Run AI triage on alert data")
async def triage_alert(body: ManualTriageRequest):
    """Manually trigger AI triage — useful for testing the Groq/Mistral pipeline."""
    weather = await get_weather(body.lat, body.lng) if body.use_weather else None
    result = await run_triage(
        alert_id=body.alert_id,
        vessel_id=body.vessel_id,
        vessel_name=body.vessel_name,
        lat=body.lat,
        lng=body.lng,
        alert_type=body.alert_type,
        weather_data=weather,
    )
    return {"triage": result, "weather": weather}
