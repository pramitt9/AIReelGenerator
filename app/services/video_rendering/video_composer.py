
import os
import subprocess


def compose_video(
    video_path: str,
    audio_path: str,
    output_path: str
) -> dict:
    """Combine rendered video with the final mixed audio."""

    for path, label in [
        (video_path, "Video"),
        (audio_path, "Audio")
    ]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{label} file not found: {path}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]

    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
    except FileNotFoundError as error:
        raise RuntimeError("FFmpeg was not found in PATH.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Video composition failed:\n{error.stderr[-4000:]}"
        ) from error

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Composition produced no valid output.")

    return {
        "output_path": output_path,
        "file_size": os.path.getsize(output_path)
    }
