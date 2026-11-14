import json
import os
import subprocess
import uuid
from pathlib import Path


def _probe_audio(path: str, label: str) -> tuple[float, dict]:
    """Return media duration and first audio stream metadata."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,sample_rate,channels,duration:"
        "format=duration",
        "-of", "json",
        str(Path(path).resolve()),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg or FFprobe was not found. "
            "Make sure both are installed and available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Could not inspect {label} audio:\n{error.stderr[-3000:]}"
        ) from error

    try:
        data = json.loads(result.stdout)
        streams = [
            stream for stream in data.get("streams", [])
            if stream.get("codec_type") == "audio"
        ]
        duration = float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"FFprobe returned invalid metadata for {label}.") from error

    if not streams:
        raise RuntimeError(f"{label} file does not contain an audio stream.")
    if not duration > 0:
        raise RuntimeError(f"{label} file has an invalid duration.")

    return duration, streams[0]


def mix_audio(
    narration_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.18,
    voice_volume: float = 1.0,
) -> dict:
    """
    Mix narration with ducked background music.

    The output follows the narration duration. The destination is replaced
    only after FFprobe confirms a valid audio stream and expected duration.
    """
    if not os.path.isfile(narration_path):
        raise FileNotFoundError(f"Narration file not found: {narration_path}")

    if not os.path.isfile(music_path):
        raise FileNotFoundError(f"Background music file not found: {music_path}")

    if not 0 <= music_volume <= 1:
        raise ValueError("music_volume must be between 0 and 1.")

    if not 0 <= voice_volume <= 2:
        raise ValueError("voice_volume must be between 0 and 2.")

    narration_duration, narration_stream = _probe_audio(
        narration_path, "Narration"
    )
    _probe_audio(music_path, "Background music")

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output.with_name(
        f"{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix or '.mp3'}"
    )

    filter_complex = (
        f"[0:a]aresample=44100,volume={voice_volume:.4f}[voice];"
        f"[1:a]aresample=44100,volume={music_volume:.4f}[music];"
        "[music][voice]"
        "sidechaincompress="
        "threshold=0.05:"
        "ratio=4:"
        "attack=30:"
        "release=700[ducked];"
        "[voice][ducked]"
        "amix=inputs=2:duration=first:dropout_transition=2,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", str(Path(narration_path).resolve()),
        "-stream_loop", "-1",
        "-i", str(Path(music_path).resolve()),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-vn",
        "-t", f"{narration_duration:.6f}",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        "-map_metadata", "-1",
        str(temporary_path),
    ]

    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        if (
            not temporary_path.is_file()
            or temporary_path.stat().st_size == 0
        ):
            raise RuntimeError("Audio mixing produced an empty output file.")

        actual_duration, output_stream = _probe_audio(
            str(temporary_path), "Mixed output"
        )

        tolerance = max(0.25, narration_duration * 0.01)
        if abs(actual_duration - narration_duration) > tolerance:
            raise RuntimeError(
                "Mixed audio duration does not match narration duration. "
                f"Expected about {narration_duration:.3f}s, "
                f"got {actual_duration:.3f}s "
                f"(tolerance {tolerance:.3f}s)."
            )

        if output_stream.get("codec_name") != "mp3":
            raise RuntimeError("Mixed output is not encoded as MP3.")

        if int(output_stream.get("sample_rate", 0)) != 44100:
            raise RuntimeError("Mixed output has an unexpected sample rate.")

        os.replace(temporary_path, output)

    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg or FFprobe was not found. "
            "Make sure both are installed and available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Audio processing failed:\n{error.stderr[-4000:]}"
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "output_path": str(output),
        "file_size": output.stat().st_size,
        "duration": actual_duration,
        "sample_rate": 44100,
        "music_volume": music_volume,
        "voice_volume": voice_volume,
        "ducking_enabled": True,
    }
