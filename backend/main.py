"""
TARANG — Maritime Emergency Rescue Backend
FastAPI + WebSockets + Groq AI + SQLite
Deploy or Die | Coastal Innovation Hackathon 2026
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from routes.alerts import router as alerts_router
from routes.vessels import router as vessels_router
from routes.weather import router as weather_router
from routes.triage import router as triage_router
from routes.simulate import router as simulate_router
from routes.ops import router as ops_router
from routes.voice import router as voice_router
from models.database import init_db
from services.connection_manager import ConnectionManager

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tarang")

# ── WebSocket Connection Manager (global) ─────────────────
manager = ConnectionManager()
STARTED_AT = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("🌊 TARANG backend starting up...")
    await init_db()
    logger.info("✅ Database initialised")
    yield
    logger.info("🔴 TARANG backend shutting down")


# ── FastAPI App ───────────────────────────────────────────
app = FastAPI(
    title="TARANG API",
    description="AI-powered LoRa mesh maritime rescue network API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(alerts_router,   prefix="/api/alerts",   tags=["Alerts"])
app.include_router(vessels_router,  prefix="/api/vessels",  tags=["Vessels"])
app.include_router(weather_router,  prefix="/api/weather",  tags=["Weather"])
app.include_router(triage_router,   prefix="/api/triage",   tags=["AI Triage"])
app.include_router(simulate_router, prefix="/api/simulate", tags=["Simulator"])
app.include_router(ops_router,      prefix="/api/ops",      tags=["Operations"])
app.include_router(voice_router,    prefix="/api/voice",    tags=["Voice"])

# ── Static file paths ────────────────────────────────────
import os
_base          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_frontend_path = os.path.join(_base, "frontend")

# Mount /static  →  frontend dir (for asset loading)
if os.path.exists(_frontend_path):
    app.mount("/static", StaticFiles(directory=_frontend_path), name="static")


@app.get("/", tags=["App"], response_class=FileResponse)
async def serve_app():
    """Serve the TARANG Operations Application (app.html)."""
    app_file = os.path.join(_frontend_path, "app.html")
    if os.path.exists(app_file):
        return FileResponse(app_file, media_type="text/html")
    return {"project":"TARANG","status":"operational","docs":"/docs"}


@app.get("/dashboard", tags=["App"], response_class=FileResponse)
async def serve_dashboard():
    """Serve the TARANG Control Room dashboard."""
    dash = os.path.join(_frontend_path, "dashboard.html")
    if os.path.exists(dash):
        return FileResponse(dash, media_type="text/html")
    return {"error": "dashboard.html not found"}


@app.get("/how-it-works", tags=["App"], response_class=FileResponse)
async def serve_how_it_works():
    """Serve the How It Works / judge demo page."""
    f = os.path.join(_frontend_path, "how-it-works.html")
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html")
    return {"error": "how-it-works.html not found"}


@app.get("/analytics", tags=["App"], response_class=FileResponse)
async def serve_analytics():
    """Serve the Analytics dashboard."""
    f = os.path.join(_frontend_path, "analytics.html")
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html")
    return {"error": "analytics.html not found"}


@app.get("/vessels", tags=["App"], response_class=FileResponse)
async def serve_vessels():
    """Serve the Vessel Registry page."""
    f = os.path.join(_frontend_path, "vessels.html")
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html")
    return {"error": "vessels.html not found"}


@app.get("/health", tags=["Health"])
async def health():
    now = datetime.utcnow()
    return {
        "status": "ok",
        "service": "tarang-backend",
        "uptime_seconds": int((now - STARTED_AT).total_seconds()),
        "websocket_clients": manager.count,
        "timestamp": now.isoformat() + "Z",
    }


# ── WebSocket: Real-time Dashboard Feed ───────────────────
@app.websocket("/ws/dashboard")
async def websocket_dashboard(ws: WebSocket):
    """
    Real-time WebSocket endpoint for the control-room dashboard.
    Broadcasts alert events, vessel position updates, and dispatch confirmations.
    """
    await manager.connect(ws)
    logger.info(f"📡 Dashboard client connected. Total: {manager.count}")
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Echo acknowledgements back to sender
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong", "ts": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info(f"📴 Dashboard client disconnected. Total: {manager.count}")


# ── Expose manager so routes can broadcast ────────────────
app.state.ws_manager = manager


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
