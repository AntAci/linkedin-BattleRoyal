"""ElevenLabs TTS integration for battle commentary."""

import os
import requests
from pathlib import Path


def get_elevenlabs_config():
    """Return API key and voice ID, or (None, None) if not configured."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    if not api_key or api_key == "your-elevenlabs-key-here":
        return None, None
    return api_key, voice_id


def synthesize_speech(text: str, output_path: str, api_key: str, voice_id: str) -> bool:
    """Generate speech audio from text using ElevenLabs API.

    Returns True on success, False on failure.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.5,
            "use_speaker_boost": True,
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return True
        else:
            print(f"ElevenLabs TTS error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"ElevenLabs TTS exception: {e}")
        return False
