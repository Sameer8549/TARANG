"""Vessels router — CRUD for registered fishing vessels."""

import logging
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import aiosqlite

from models.schemas import VesselUpdate
from models.database import get_db

router = APIRouter()
logger = logging.getLogger("tarang.vessels")


@router.get("", summary="List all registered vessels")
async def list_vessels(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM vessels ORDER BY name") as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{vessel_id}", summary="Get vessel by ID")
async def get_vessel(vessel_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM vessels WHERE id=?", (vessel_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Vessel not found")
    return dict(row)


@router.patch("/{vessel_id}/position", summary="Update vessel GPS position")
async def update_position(
    vessel_id: str, body: VesselUpdate, db: aiosqlite.Connection = Depends(get_db)
):
    await db.execute(
        "UPDATE vessels SET lat=?, lng=?, last_seen=? WHERE id=?",
        (body.lat, body.lng, datetime.utcnow().isoformat(), vessel_id),
    )
    await db.commit()
    return {"success": True, "vessel_id": vessel_id}
