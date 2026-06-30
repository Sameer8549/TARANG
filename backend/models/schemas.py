"""Pydantic schemas for TARANG API."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    SOS_MANUAL    = "sos_manual"
    CAPSIZE       = "capsize"
    DRIFT         = "drift"
    ENGINE_FAIL   = "engine_fail"
    MEDICAL       = "medical"
    FIRE          = "fire"


class SeverityLevel(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE     = "active"
    TRIAGED    = "triaged"
    DISPATCHED = "dispatched"
    RESOLVED   = "resolved"


# ── Request Schemas ───────────────────────────────────────

class SOSPayload(BaseModel):
    """Payload sent by ESP32/LoRa device when SOS triggered."""
    vessel_id:   str = Field(..., example="VES-001")
    lat:         float = Field(..., example=12.889)
    lng:         float = Field(..., example=74.842)
    alert_type:  AlertType = AlertType.SOS_MANUAL
    battery_pct: Optional[int] = Field(None, ge=0, le=100)
    accel_x:     Optional[float] = None
    accel_y:     Optional[float] = None
    accel_z:     Optional[float] = None
    speed_kmh:   Optional[float] = None
    heading_deg: Optional[float] = None
    rssi:        Optional[int]   = None
    hop_count:   Optional[int]   = Field(0, ge=0)


class DispatchAction(BaseModel):
    alert_id: str
    action:   str  # "dispatch_coast_guard" | "dispatch_nearby" | "sms_family" | "resolve"
    operator: Optional[str] = "control_room"
    note:     Optional[str] = None


class VesselUpdate(BaseModel):
    lat:      float
    lng:      float
    speed:    Optional[float] = None
    heading:  Optional[float] = None
    battery:  Optional[int]   = None


# ── Response Schemas ──────────────────────────────────────

class VesselOut(BaseModel):
    id:        str
    name:      str
    owner:     Optional[str]
    phone:     Optional[str]
    lat:       Optional[float]
    lng:       Optional[float]
    last_seen: Optional[str]
    status:    str


class AlertOut(BaseModel):
    id:           str
    vessel_id:    str
    vessel_name:  Optional[str]
    lat:          float
    lng:          float
    alert_type:   str
    severity:     str
    status:       str
    ai_summary:   Optional[str]
    ai_responder: Optional[str]
    distance_km:  Optional[float]
    weather_risk: Optional[str]
    created_at:   str
    resolved_at:  Optional[str]


class TriageResult(BaseModel):
    alert_id:     str
    severity:     SeverityLevel
    summary:      str
    recommended_action: str
    nearest_responder:  str
    estimated_eta_min:  int
    weather_risk: str
    confidence:   float
