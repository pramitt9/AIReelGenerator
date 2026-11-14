
import json
import os
import subprocess
import uuid
from pathlib import Path

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from flask import current_app


def build_narration_text(storyboard: dict) -> str:
    """Assemble hook, scene narrations and ending into one narration."""

    if not isinstance(storyboard, dict):
        raise ValueError("Invalid storyboard format.")

    scenes = storyboard.get("scenes", [])

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Storyboard contains no scenes.")

    narration_parts = []

    hook = storyboard.get("hook", "")

    if hook:
        if not isinstance(hook, str):
            raise ValueError("Storyboard hook must be text.")

        if hook.strip():
            narration_parts.append(hook.strip())

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


def validate_audio_file(audio_path: Path) -> dict:
    """Verify that FFprobe can read the generated audio file."""

    if not audio_path.is_file() or audio_path.stat().st_size == 0:
        raise RuntimeError("Generated narration file is missing or empty.")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-show_entries", "format=duration",
                "-of", "json",
                str(audio_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )

    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFprobe was not found. Make sure FFmpeg is installed "
            "and available in PATH."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFprobe could not validate narration: {exc.stderr.strip()}"
        ) from exc

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned invalid audio metadata.") from exc

    streams = metadata.get("streams", [])
    audio_streams = [
        stream for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    if not audio_streams:
        raise RuntimeError("Generated file contains no valid audio stream.")

    duration = float(metadata.get("format", {}).get("duration", 0))

    if duration <= 0:
        raise RuntimeError("Generated narration has an invalid duration.")

    return {
        "duration": duration,
        "codec": audio_streams[0].get("codec_name")
    }


def generate_narration(
    storyboard: dict,
    project_id: int,
    output_path: str | None = None
) -> dict:
    """
    Generate complete narration audio from the storyboard.

    Supports a custom output path for isolated generation jobs.
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

    if output_path:
        final_path = Path(output_path)
    else:
        storage_dir = (
            Path(current_app.root_path).parent
            / "storage"
            / "audio"
            / f"project_{project_id}"
        )
        final_path = storage_dir / "narration.mp3"

    final_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = final_path.with_name(
        f"{final_path.stem}.{uuid.uuid4().hex}.tmp.mp3"
    )

    try:
        with temporary_path.open("wb") as audio_file:
            for chunk in response:
                if chunk:
                    audio_file.write(chunk)

        audio_metadata = validate_audio_file(temporary_path)

        # Replace the destination only after the new audio is validated.
        os.replace(temporary_path, final_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "project_id": project_id,
        "audio_path": str(final_path.resolve()),
        "narration": narration,
        "file_size": final_path.stat().st_size,
        "duration": audio_metadata["duration"],
        "codec": audio_metadata["codec"],
        "voice_id": voice_id
    }
