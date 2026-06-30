"""
AI Triage Service — uses Groq (primary) and Mistral (fallback) to score
and summarise incoming maritime distress alerts.
"""

import os
import logging
import math
from datetime import datetime
from typing import Optional

logger = logging.getLogger("tarang.ai")

# ── Groq Client ───────────────────────────────────────────
try:
    from groq import AsyncGroq
    groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq package not installed — falling back to Mistral/heuristic")

# ── Mistral Client ────────────────────────────────────────
try:
    from mistralai import Mistral
    mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ""))
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    logger.warning("mistralai package not installed — using heuristic fallback")


SHORE_LAT = 12.8698   # Mangaluru shore reference point
SHORE_LNG = 74.8431

SEVERITY_WEIGHTS = {
    "capsize":      1.0,
    "sos_manual":   0.9,
    "fire":         0.95,
    "medical":      0.85,
    "drift":        0.65,
    "engine_fail":  0.55,
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _heuristic_severity(alert_type: str, dist_km: float, weather_risk: str) -> str:
    base = SEVERITY_WEIGHTS.get(alert_type, 0.6)
    dist_factor = min(dist_km / 20.0, 1.0) * 0.2
    weather_factor = {"low": 0, "moderate": 0.1, "high": 0.2, "extreme": 0.3}.get(weather_risk, 0)
    score = base + dist_factor + weather_factor
    if score >= 0.95:   return "critical"
    elif score >= 0.75: return "high"
    elif score >= 0.55: return "medium"
    else:               return "low"


async def run_triage(
    alert_id: str,
    vessel_id: str,
    vessel_name: str,
    lat: float,
    lng: float,
    alert_type: str,
    weather_data: Optional[dict] = None,
) -> dict:
    """
    Core triage function. Returns severity, summary, recommended action, responder ETA.
    Tries Groq → Mistral → heuristic fallback.
    """
    dist_km = haversine_km(lat, lng, SHORE_LAT, SHORE_LNG)
    weather_risk = _assess_weather_risk(weather_data)
    severity = _heuristic_severity(alert_type, dist_km, weather_risk)
    eta_min = max(15, int(dist_km * 4))  # ~15 km/h coast guard boat

    prompt = _build_prompt(alert_id, vessel_id, vessel_name, lat, lng,
                           alert_type, dist_km, weather_risk, severity)

    ai_summary = None
    ai_responder = None

    # ── Try Groq (llama-3.3-70b-versatile) ───────────────
    if GROQ_AVAILABLE and os.getenv("GROQ_API_KEY"):
        try:
            response = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are TARANG AI — a maritime rescue triage agent. Respond ONLY with valid JSON."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            raw = response.choices[0].message.content.strip()
            parsed = _parse_ai_response(raw)
            ai_summary = parsed.get("summary", "")
            ai_responder = parsed.get("responder", "")
            severity = parsed.get("severity", severity)
            logger.info(f"✅ Groq triage done for {alert_id}")
        except Exception as e:
            logger.warning(f"Groq failed: {e} — trying Mistral")

    # ── Try Mistral fallback ──────────────────────────────
    if not ai_summary and MISTRAL_AVAILABLE and os.getenv("MISTRAL_API_KEY"):
        try:
            response = mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": "You are TARANG AI — a maritime rescue triage agent. Respond ONLY with valid JSON."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            raw = response.choices[0].message.content.strip()
            parsed = _parse_ai_response(raw)
            ai_summary = parsed.get("summary", "")
            ai_responder = parsed.get("responder", "")
            severity = parsed.get("severity", severity)
            logger.info(f"✅ Mistral triage done for {alert_id}")
        except Exception as e:
            logger.warning(f"Mistral failed: {e} — using heuristic only")

    # ── Final heuristic fallback ──────────────────────────
    if not ai_summary:
        ai_summary = _heuristic_summary(vessel_name, alert_type, dist_km, weather_risk, severity)
        ai_responder = _heuristic_responder(dist_km, severity)

    return {
        "alert_id":     alert_id,
        "severity":     severity,
        "summary":      ai_summary,
        "ai_responder": ai_responder,
        "distance_km":  round(dist_km, 2),
        "weather_risk": weather_risk,
        "eta_min":      eta_min,
        "confidence":   0.92 if ai_summary else 0.7,
    }


def _assess_weather_risk(weather_data: Optional[dict]) -> str:
    if not weather_data:
        return "moderate"
    wind = weather_data.get("wind_speed_ms", 5)
    wave = weather_data.get("wave_height_m", 1.0)
    if wind > 15 or wave > 3:   return "extreme"
    elif wind > 10 or wave > 2: return "high"
    elif wind > 6  or wave > 1: return "moderate"
    return "low"


def _build_prompt(alert_id, vessel_id, vessel_name, lat, lng,
                  alert_type, dist_km, weather_risk, severity) -> str:
    return f"""
Maritime emergency received. Triage this alert and respond in JSON.

Alert ID:    {alert_id}
Vessel:      {vessel_name} ({vessel_id})
Position:    {lat:.4f}°N, {lng:.4f}°E
Distance:    {dist_km:.1f} km from shore (Mangaluru)
Alert Type:  {alert_type}
Weather:     {weather_risk} risk
Initial sev: {severity}
Time (UTC):  {datetime.utcnow().strftime('%H:%M')}

Respond ONLY in this JSON format:
{{
  "severity": "critical|high|medium|low",
  "summary": "2-sentence incident summary for control room operator",
  "responder": "Nearest recommended responder name/unit",
  "action": "Specific recommended immediate action"
}}
"""


def _parse_ai_response(raw: str) -> dict:
    import json, re
    # Extract JSON from response
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def _heuristic_summary(vessel_name, alert_type, dist_km, weather_risk, severity) -> str:
    type_map = {
        "capsize":    f"{vessel_name} has capsized",
        "sos_manual": f"{vessel_name} sent a manual SOS",
        "drift":      f"{vessel_name} is drifting uncontrolled",
        "fire":       f"Fire reported aboard {vessel_name}",
        "medical":    f"Medical emergency aboard {vessel_name}",
        "engine_fail":f"{vessel_name} reports engine failure",
    }
    base = type_map.get(alert_type, f"Emergency from {vessel_name}")
    return (f"{base}, {dist_km:.1f} km offshore. "
            f"Weather risk: {weather_risk}. Severity classified {severity.upper()}. "
            f"Immediate response recommended.")


def _heuristic_responder(dist_km: float, severity: str) -> str:
    if severity in ("critical", "high") or dist_km > 12:
        return "ICG Mangalore — Fast Patrol Vessel C-156"
    elif dist_km > 6:
        return "NDRF Coastal Unit — Mangaluru"
    return "Nearest registered fishing vessel + local harbour patrol"
