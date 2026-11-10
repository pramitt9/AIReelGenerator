
import os
from pathlib import Path

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from flask import current_app


def generate_narration(
    storyboard: dict,
    project_id: int
) -> dict:
    """
    Generate narration audio from the complete storyboard.
    Returns audio file metadata.
    """

    api_key = current_app.config.get("ELEVENLABS_API_KEY")

    if not api_key:
        raise ValueError("ElevenLabs API key is not configured.")

    scenes = storyboard.get("scenes", [])

    if not scenes:
        raise ValueError("Storyboard contains no scenes.")

    narration = " ".join(
        scene["narration"].strip()
        for scene in scenes
        if scene.get("narration")
    )

    if not narration.strip():
        raise ValueError("No narration text available.")

    client = ElevenLabs(api_key=api_key)

    voice_id = "pNInz6obpgDQGcFmaJgB"

    response = client.text_to_speech.convert(
        voice_id=voice_id,
        output_format="mp3_44100_128",
        text=narration,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True
        )
    )

    storage_dir = (
        Path(current_app.root_path)
        .parent / "storage" / "audio" / f"project_{project_id}"
    )

    storage_dir.mkdir(parents=True, exist_ok=True)

    output_path = storage_dir / "narration.mp3"
    temporary_path = storage_dir / "narration.tmp.mp3"

    try:
        with temporary_path.open("wb") as audio_file:
            for chunk in response:
                if chunk:
                    audio_file.write(chunk)

        if not temporary_path.exists() or temporary_path.stat().st_size == 0:
            raise RuntimeError("ElevenLabs returned an empty audio file.")

        os.replace(temporary_path, output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "project_id": project_id,
        "audio_path": str(output_path.resolve()),
        "narration": narration,
        "file_size": output_path.stat().st_size,
        "voice_id": voice_id
    }
