"""
Operations Router - readiness and SAR playbook endpoints.
These endpoints keep the demo grounded in a real control-room workflow.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
import aiosqlite

from models.database import get_db

router = APIRouter()


@router.get("/readiness", summary="Operational readiness summary")
async def readiness(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT COUNT(*) AS n FROM vessels") as cur:
        vessels = (await cur.fetchone())["n"]

    async with db.execute("SELECT COUNT(*) AS n FROM alerts WHERE status='active'") as cur:
        active_alerts = (await cur.fetchone())["n"]

    async with db.execute("SELECT COUNT(*) AS n FROM alerts WHERE status='dispatched'") as cur:
        dispatched = (await cur.fetchone())["n"]

    async with db.execute("SELECT COUNT(*) AS n FROM alerts WHERE status='resolved'") as cur:
        resolved = (await cur.fetchone())["n"]

    async with db.execute(
        "SELECT id, vessel_name, alert_type, severity, distance_km, created_at "
        "FROM alerts WHERE status='active' "
        "ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
        "WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC LIMIT 1"
    ) as cur:
        top_alert = await cur.fetchone()

    if active_alerts:
        readiness_state = "degraded"
        recommendation = "Keep MRSC New Mangalore on command-post mode and dispatch the highest-severity alert first."
    else:
        readiness_state = "ready"
        recommendation = "System ready. Continue watch, weather polling, and vessel heartbeat monitoring."

    return {
        "status": readiness_state,
        "zone": "Karnataka Coast - Mangaluru / New Mangalore",
        "mrcc": "MRCC Mumbai",
        "mrsc": "MRSC New Mangalore",
        "vessels_tracked": vessels,
        "active_alerts": active_alerts,
        "dispatched_alerts": dispatched,
        "resolved_alerts": resolved,
        "top_priority": dict(top_alert) if top_alert else None,
        "recommendation": recommendation,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/playbook", summary="Maritime rescue workflow")
async def playbook():
    return {
        "name": "TARANG coastal SAR playbook",
        "principles": [
            "Preserve location, vessel identity, alert type, battery and LoRa hop metadata.",
            "Prioritise capsize, fire, medical emergency and long offshore distance as critical signals.",
            "Route verified distress to MRSC New Mangalore / MRCC Mumbai while notifying family contacts.",
            "Use nearby vessels as first responders when they are closer than a patrol craft.",
            "Keep an operator audit trail for every dispatch, family notification and resolution action.",
        ],
        "stages": [
            {"id": 1, "stage": "Detect", "owner": "Boat device", "target_seconds": 10},
            {"id": 2, "stage": "Relay", "owner": "LoRa mesh / shore node", "target_seconds": 60},
            {"id": 3, "stage": "Triage", "owner": "TARANG AI + operator", "target_seconds": 30},
            {"id": 4, "stage": "Coordinate", "owner": "MRSC New Mangalore / MRCC Mumbai", "target_seconds": 120},
            {"id": 5, "stage": "Dispatch", "owner": "ICG / nearest vessel / port authority", "target_seconds": 180},
            {"id": 6, "stage": "Resolve", "owner": "Control room", "target_seconds": None},
        ],
        "demo_note": "This prototype simulates the upstream LoRa packet and demonstrates alert triage, map display, WebSocket broadcast and dispatch logging.",
    }
