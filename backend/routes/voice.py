"""
Server-side voice generation for operator/profile audio.

Uses Azure AI Speech when AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are set.
When no paid key is configured, it falls back to a no-key Kannada TTS request.
The dashboard also has bundled Kannada clips, so Kannada mode never falls back
to an English browser voice.
"""

import os
from html import escape

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)
    lang: str = Field("kn", pattern="^(kn|en)$")


VOICE_BY_LANG = {
    "kn": ("kn-IN", "kn-IN-SapnaNeural"),
    "en": ("en-IN", "en-IN-NeerjaNeural"),
}


@router.post("/tts", summary="Generate distress voice audio")
async def text_to_speech(payload: TTSRequest):
    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        return await no_key_tts(payload)

    locale, voice = VOICE_BY_LANG[payload.lang]
    ssml = f"""
<speak version="1.0" xml:lang="{locale}" xmlns="http://www.w3.org/2001/10/synthesis">
  <voice xml:lang="{locale}" name="{voice}">
    <prosody rate="-4%" pitch="+0%">{escape(payload.text)}</prosody>
  </voice>
</speak>
""".strip()

    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "tarang-rescue-dashboard",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(url, headers=headers, content=ssml.encode("utf-8"))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"TTS provider unavailable: {exc}") from exc

    if res.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"TTS provider error: {res.status_code}")

    return Response(
        content=res.content,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


async def no_key_tts(payload: TTSRequest):
    lang = "kn" if payload.lang == "kn" else "en"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                "https://translate.google.com/translate_tts",
                params={
                    "ie": "UTF-8",
                    "client": "tw-ob",
                    "tl": lang,
                    "q": payload.text,
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                    )
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"No-key TTS unavailable: {exc}") from exc

    content_type = res.headers.get("content-type", "")
    if res.status_code >= 400 or "audio" not in content_type:
        raise HTTPException(status_code=502, detail=f"No-key TTS error: {res.status_code}")

    return Response(
        content=res.content,
        media_type=content_type.split(";")[0] or "audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
