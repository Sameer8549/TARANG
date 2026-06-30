"""
SMS + Voice Alert Service using Twilio.
Sends multilingual alerts (Kannada, Tulu, Malayalam, Hindi, English).
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("tarang.sms")

try:
    from twilio.rest import Client as TwilioClient
    twilio_client = TwilioClient(
        os.getenv("TWILIO_ACCOUNT_SID", ""),
        os.getenv("TWILIO_AUTH_TOKEN", ""),
    )
    TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER", "+15005550006")
    TWILIO_AVAILABLE = True
except Exception:
    TWILIO_AVAILABLE = False
    logger.warning("Twilio not configured — SMS/Voice alerts will be logged only")


MESSAGES = {
    "en": "TARANG ALERT: {vessel_name} has sent a distress signal at {lat:.4f}°N, {lng:.4f}°E. Emergency services notified. Stay calm.",
    "kn": "ತರಂಗ ಎಚ್ಚರಿಕೆ: {vessel_name} ತೊಂದರೆ ಸಂಕೇತ ಕಳುಹಿಸಿದೆ. ರಕ್ಷಣೆ ಹೊರಟಿದೆ.",
    "ml": "താരംഗ് അലേർട്ട്: {vessel_name} ദുരിതകരമായ ഒരു സൂചന അയച്ചിരിക്കുന്നു. ദുരന്ത നിവാരണ സേന ഇറങ്ങിക്കഴിഞ്ഞു.",
    "hi": "TARANG चेतावनी: {vessel_name} ने संकट संकेत भेजा है। बचाव दल रवाना हो गया है।",
}


async def send_sms_alert(
    to_number: str,
    vessel_name: str,
    lat: float,
    lng: float,
    language: str = "en",
) -> bool:
    """Send SMS alert to vessel owner / family."""
    template = MESSAGES.get(language, MESSAGES["en"])
    body = template.format(vessel_name=vessel_name, lat=lat, lng=lng)

    logger.info(f"📱 SMS → {to_number}: {body[:80]}...")

    if not TWILIO_AVAILABLE:
        logger.info("[MOCK SMS] Would send to %s", to_number)
        return True

    try:
        msg = twilio_client.messages.create(
            body=body,
            from_=TWILIO_FROM,
            to=to_number,
        )
        logger.info(f"✅ SMS sent: {msg.sid}")
        return True
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        return False


async def send_voice_alert(
    to_number: str,
    vessel_name: str,
    lat: float,
    lng: float,
) -> bool:
    """Send TwiML voice call with alert."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en-IN">
    TARANG Emergency Alert. {vessel_name} has sent a distress signal at
    {lat:.2f} degrees North, {lng:.2f} degrees East.
    Emergency rescue services have been notified.
    Please stay calm and await rescue.
    This is an automated message from Team Cipher TARANG.
  </Say>
</Response>"""

    logger.info(f"📞 Voice call → {to_number}")

    if not TWILIO_AVAILABLE:
        logger.info("[MOCK CALL] Would call %s", to_number)
        return True

    try:
        call = twilio_client.calls.create(
            twiml=twiml,
            from_=TWILIO_FROM,
            to=to_number,
        )
        logger.info(f"✅ Voice call initiated: {call.sid}")
        return True
    except Exception as e:
        logger.error(f"Voice call failed: {e}")
        return False
