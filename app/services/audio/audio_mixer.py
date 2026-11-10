
import os
import subprocess


def mix_audio(
    narration_path:str,
    music_path: str,
    output_path :str,
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

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

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
        "-i", narration_path,
        "-stream_loop", "-1",
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        output_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg was not found. Make sure FFmpeg is installed "
            "and available in PATH."
        )

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Audio mixing failed:\n{error.stderr[-3000:]}"
        ) from error

    return {
        "output_path": output_path,
        "file_size": os.path.getsize(output_path),
        "music_volume": music_volume,
        "voice_volume": voice_volume,
        "ducking_enabled": True
    }
