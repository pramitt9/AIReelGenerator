
import os
import subprocess


def render_video(
    timeline: dict,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30
) -> dict:
    """
    Render video scenes according to a synchronized timeline.

    Each timeline scene must contain:
        asset_path
        start
        end
        duration
    """

    scenes = timeline.get("scenes", [])

    if not scenes:
        raise ValueError("Timeline contains no scenes.")

    total_duration = float(timeline["total_duration"])

    if total_duration <= 0:
        raise ValueError("Invalid timeline duration.")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    command = ["ffmpeg", "-y"]
    filters = []

    for index, scene in enumerate(scenes):
        asset_path = scene.get("asset_path")

        if not asset_path or not os.path.isfile(asset_path):
            raise FileNotFoundError(
                f"Video file missing for scene {scene.get('scene_number')}: "
                f"{asset_path}"
            )

        start = float(scene["start"])
        end = float(scene["end"])

        if start < 0 or end <= start or end > total_duration + 0.01:
            raise ValueError(
                f"Invalid timing for scene {scene.get('scene_number')}."
            )

        duration = end - start

        command.extend([
            "-stream_loop", "-1",
            "-i", asset_path
        ])

        filters.append(
            f"[{index}:v]"
            f"trim=duration={duration:.6f},"
            "setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            "setsar=1,"
            "format=yuv420p"
            f"[v{index}]"
        )

    input_labels = "".join(
        f"[v{index}]" for index in range(len(scenes))
    )

    filters.append(
        f"{input_labels}"
        f"concat=n={len(scenes)}:v=1:a=0[outv]"
    )

    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
        "-an",
        "-t", f"{total_duration:.6f}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ])

    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg was not found. Check that it is installed and in PATH."
        ) from error

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Video rendering failed:\n{error.stderr[-4000:]}"
        ) from error

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Rendering produced no valid output.")

    return {
        "output_path": output_path,
        "file_size": os.path.getsize(output_path),
        "scene_count": len(scenes),
        "resolution": f"{width}x{height}",
        "fps": fps,
        "duration": total_duration
    }
