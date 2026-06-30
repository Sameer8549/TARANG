"""
Simulation router — fires realistic SOS events for demo purposes.
POST /api/simulate/sos    — single SOS event
POST /api/simulate/fleet  — continuous multi-vessel simulation
"""

import asyncio
import random
import logging
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Request

router = APIRouter()
logger = logging.getLogger("tarang.simulate")

# ── Mangaluru coastal bounding box ────────────────────────
LAT_MIN, LAT_MAX = 12.72, 13.05
LNG_MIN, LNG_MAX = 74.50, 74.95

VESSEL_IDS = ["VES-001", "VES-002", "VES-003", "VES-004", "VES-005"]
ALERT_TYPES = ["sos_manual", "capsize", "drift", "engine_fail", "medical"]


def random_coastal_position():
    return round(random.uniform(LAT_MIN, LAT_MAX), 4), round(random.uniform(LNG_MIN, LNG_MAX), 4)


@router.post("/sos", summary="Fire single simulated SOS alert")
async def simulate_sos(request: Request, background_tasks: BackgroundTasks):
    """Fires a single randomised SOS alert through the full pipeline."""
    vessel_id  = random.choice(VESSEL_IDS)
    alert_type = random.choice(ALERT_TYPES)
    lat, lng   = random_coastal_position()

    # Call the actual SOS ingestion pipeline
    from routes.alerts import ingest_sos
    from models.schemas import SOSPayload, AlertType

    try:
        at_enum = AlertType(alert_type)
    except ValueError:
        at_enum = AlertType.SOS_MANUAL

    payload = SOSPayload(
        vessel_id=vessel_id,
        lat=lat,
        lng=lng,
        alert_type=at_enum,
        battery_pct=random.randint(20, 95),
        hop_count=random.randint(0, 3),
        rssi=random.randint(-120, -60),
    )

    # We need a real DB dependency — run inline
    import aiosqlite, os
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tarang.db")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        result = await ingest_sos(payload, request, db)

    logger.info(f"🎮 Simulation: {result['alert_id']}")
    return {"simulated": True, "result": result}


@router.post("/fleet", summary="Run multi-vessel simulation loop")
async def simulate_fleet(request: Request, background_tasks: BackgroundTasks, count: int = 3):
    """Fires `count` SOS alerts with 2s delay between each."""

    async def _run():
        for i in range(min(count, 10)):
            await asyncio.sleep(2)
            try:
                from routes.simulate import simulate_sos
                await simulate_sos(request, background_tasks)
            except Exception as e:
                logger.error(f"Fleet sim step {i} failed: {e}")

    background_tasks.add_task(_run)
    return {"message": f"Fleet simulation started — {count} alerts will fire over {count * 2}s"}


@router.get("/vessels/positions", summary="Get live simulated vessel positions")
async def simulated_positions():
    """Returns randomised vessel positions for map rendering."""
    positions = []
    for vid in VESSEL_IDS:
        lat, lng = random_coastal_position()
        positions.append({
            "vessel_id": vid,
            "lat": lat,
            "lng": lng,
            "heading": random.randint(0, 359),
            "speed_kmh": round(random.uniform(4, 18), 1),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        })
    return positions
