
import os
from pathlib import Path

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from flask import current_app


def build_narration_text(storyboard: dict) -> str:
    """
    Assemble the complete spoken narration.

    Order:
    1. Opening hook
    2. Scene narrations
    3. Ending
    """

    if not isinstance(storyboard, dict):
        raise ValueError("Invalid storyboard format.")

    scenes = storyboard.get("scenes", [])

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Storyboard contains no scenes.")

    narration_parts = []

    # Opening hook
    hook = storyboard.get("hook", "")

    if hook:
        if not isinstance(hook, str):
            raise ValueError("Storyboard hook must be text.")

        if hook.strip():
            narration_parts.append(hook.strip())

    # Scene narrations
    for index, scene in enumerate(scenes, start=1):

        if not isinstance(scene, dict):
            raise ValueError(f"Invalid scene data at position {index}.")

        scene_narration = scene.get("narration", "")

        if not isinstance(scene_narration, str) or not scene_narration.strip():
            raise ValueError(
                f"Scene {scene.get('scene_number', index)} "
                "has no valid narration."
            )

        narration_parts.append(scene_narration.strip())

    # Ending
    ending = storyboard.get("ending", "")

    if ending:
        if not isinstance(ending, str):
            raise ValueError("Storyboard ending must be text.")

        if ending.strip():
            narration_parts.append(ending.strip())

    narration = " ".join(narration_parts).strip()

    if not narration:
        raise ValueError("No narration text available.")

    return narration


def generate_narration(
    storyboard: dict,
    project_id: int
) -> dict:
    """
    Generate complete narration audio from the storyboard.

    Includes the opening hook, scene narrations and ending.

    Returns audio file metadata.
    """

    api_key = current_app.config.get("ELEVENLABS_API_KEY")

    if not api_key:
        raise ValueError("ElevenLabs API key is not configured.")

    narration = build_narration_text(storyboard)

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
        Path(current_app.root_path).parent
        / "storage"
        / "audio"
        / f"project_{project_id}"
    )

    storage_dir.mkdir(parents=True, exist_ok=True)

    output_path = storage_dir / "narration.mp3"
    temporary_path = storage_dir / "narration.tmp.mp3"

    try:
        with temporary_path.open("wb") as audio_file:
            for chunk in response:
                if chunk:
                    audio_file.write(chunk)

        if (
            not temporary_path.exists()
            or temporary_path.stat().st_size == 0
        ):
            raise RuntimeError(
                "ElevenLabs returned an empty audio file."
            )

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
