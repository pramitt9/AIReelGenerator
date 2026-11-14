
import os
import subprocess
import uuid
from pathlib import Path


def mix_audio(
    narration_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.18,
    voice_volume: float = 1.0,
) -> dict:
    """
    Mix narration with background music.

    Background music automatically ducks when narration is playing.
    Output duration follows the narration.
    """

    if not os.path.isfile(narration_path):
        raise FileNotFoundError(
            f"Narration file not found: {narration_path}"
        )

    if not os.path.isfile(music_path):
        raise FileNotFoundError(
            f"Background music file not found: {music_path}"
        )

    if not 0 <= music_volume <= 1:
        raise ValueError("music_volume must be between 0 and 1.")

    if not 0 <= voice_volume <= 2:
        raise ValueError("voice_volume must be between 0 and 2.")

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output.with_name(
        f"{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix}"
    )

    filter_complex = (
        f"[0:a]volume={voice_volume}[voice];"
        f"[1:a]volume={music_volume}[music];"
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
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        str(temporary_path)
    ]

    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        if (
            not temporary_path.is_file()
            or temporary_path.stat().st_size == 0
        ):
            raise RuntimeError(
                "Audio mixing produced an empty output file."
            )

        # Verify that FFprobe can read an audio stream.
        probe_command = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(temporary_path)
        ]

        probe_result = subprocess.run(
            probe_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        if "audio" not in probe_result.stdout.lower():
            raise RuntimeError(
                "Mixed audio does not contain a valid audio stream."
            )

        # Promote the validated file.
        os.replace(temporary_path, output)

    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg or FFprobe was not found. "
            "Make sure both are installed and available in PATH."
        ) from error

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Audio processing failed:\n{error.stderr[-3000:]}"
        ) from error

    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "output_path": str(output),
        "file_size": output.stat().st_size,
        "music_volume": music_volume,
        "voice_volume": voice_volume,
        "ducking_enabled": True
    }
