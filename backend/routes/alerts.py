"""
Alerts Router — the core SOS ingestion + query endpoint.
POST /api/alerts/sos  — device sends distress signal
GET  /api/alerts      — list all alerts (dashboard)
GET  /api/alerts/{id} — single alert detail
PATCH /api/alerts/{id}/status — update alert status
"""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
import aiosqlite

from models.schemas import SOSPayload, AlertOut, DispatchAction
from models.database import get_db
from services.ai_triage import run_triage
from services.weather_service import get_weather
from services.sms_service import send_sms_alert, send_voice_alert

router = APIRouter()
logger = logging.getLogger("tarang.alerts")


@router.post("/sos", summary="Ingest SOS alert from LoRa device")
async def ingest_sos(payload: SOSPayload, request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """
    Called by shore station when LoRa packet arrives.
    1. Look up vessel info
    2. Fetch weather for coordinates
    3. Run AI triage
    4. Persist to DB
    5. Broadcast to WebSocket clients
    6. Send SMS/voice to family
    """
    alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"🆘 SOS received: {alert_id} from {payload.vessel_id} @ {payload.lat},{payload.lng}")

    # ── Fetch vessel info ─────────────────────────────────
    async with db.execute("SELECT * FROM vessels WHERE id = ?", (payload.vessel_id,)) as cur:
        vessel = await cur.fetchone()

    if not vessel:
        # Auto-register unknown vessel
        vessel_name = f"Unknown-{payload.vessel_id}"
        vessel_phone = None
    else:
        vessel_name = vessel["name"]
        vessel_phone = vessel["phone"]
        # Update vessel position
        await db.execute(
            "UPDATE vessels SET lat=?, lng=?, last_seen=?, status='active' WHERE id=?",
            (payload.lat, payload.lng, datetime.utcnow().isoformat(), payload.vessel_id),
        )

    # ── Fetch weather ─────────────────────────────────────
    weather = await get_weather(payload.lat, payload.lng)

    # ── Run AI triage ─────────────────────────────────────
    triage = await run_triage(
        alert_id=alert_id,
        vessel_id=payload.vessel_id,
        vessel_name=vessel_name,
        lat=payload.lat,
        lng=payload.lng,
        alert_type=payload.alert_type.value,
        weather_data=weather,
    )

    # ── Persist alert ─────────────────────────────────────
    await db.execute("""
        INSERT INTO alerts
            (id, vessel_id, vessel_name, lat, lng, alert_type, severity,
             status, ai_summary, ai_responder, distance_km, weather_risk, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        alert_id, payload.vessel_id, vessel_name,
        payload.lat, payload.lng, payload.alert_type.value,
        triage["severity"], "active",
        triage["summary"], triage["ai_responder"],
        triage["distance_km"], triage["weather_risk"],
        datetime.utcnow().isoformat(),
    ))

    # Record mesh hops
    if payload.hop_count and payload.hop_count > 0:
        await db.execute("""
            INSERT INTO mesh_hops (alert_id, relay_id, lat, lng, rssi)
            VALUES (?,?,?,?,?)
        """, (alert_id, payload.vessel_id, payload.lat, payload.lng, payload.rssi))

    await db.commit()

    # ── Broadcast via WebSocket ───────────────────────────
    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast("new_alert", {
        "alert_id":    alert_id,
        "vessel_id":   payload.vessel_id,
        "vessel_name": vessel_name,
        "lat":         payload.lat,
        "lng":         payload.lng,
        "alert_type":  payload.alert_type.value,
        "severity":    triage["severity"],
        "distance_km": triage["distance_km"],
        "ai_summary":  triage["summary"],
        "ai_responder":triage["ai_responder"],
        "weather_risk":triage["weather_risk"],
        "created_at":  datetime.utcnow().isoformat() + "Z",
    })

    # ── Send SMS/Voice to family ──────────────────────────
    if vessel_phone:
        await send_sms_alert(vessel_phone, vessel_name, payload.lat, payload.lng)
        if triage["severity"] in ("critical", "high"):
            await send_voice_alert(vessel_phone, vessel_name, payload.lat, payload.lng)

    return {
        "success":  True,
        "alert_id": alert_id,
        "triage":   triage,
        "weather":  weather,
    }


@router.get("", summary="List all alerts")
async def list_alerts(
    status: str = None,
    limit: int = 50,
    db: aiosqlite.Connection = Depends(get_db)
):
    if status:
        async with db.execute(
            "SELECT * FROM alerts WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{alert_id}", summary="Get alert by ID")
async def get_alert(alert_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    # Include hop trace
    async with db.execute(
        "SELECT * FROM mesh_hops WHERE alert_id=? ORDER BY hopped_at", (alert_id,)
    ) as cur:
        hops = [dict(h) for h in await cur.fetchall()]
    result = dict(row)
    result["mesh_hops"] = hops
    return result


@router.patch("/{alert_id}/dispatch", summary="Dispatch action on alert")
async def dispatch_alert(
    alert_id: str,
    body: DispatchAction,
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT id FROM alerts WHERE id=?", (alert_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Alert not found")

    new_status = "dispatched" if body.action != "resolve" else "resolved"
    resolved_at = datetime.utcnow().isoformat() if new_status == "resolved" else None

    await db.execute(
        "UPDATE alerts SET status=?, resolved_at=? WHERE id=?",
        (new_status, resolved_at, alert_id),
    )
    await db.execute("""
        INSERT INTO dispatch_log (alert_id, action, operator, note)
        VALUES (?,?,?,?)
    """, (alert_id, body.action, body.operator, body.note))
    await db.commit()

    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast("alert_update", {
        "alert_id": alert_id,
        "status":   new_status,
        "action":   body.action,
        "operator": body.operator,
    })

    return {"success": True, "alert_id": alert_id, "new_status": new_status}
