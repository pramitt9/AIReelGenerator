
import os
import subprocess


def render_video(
    timeline: dict,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    motion: str = "none",
    motion_strength: float = 0.08,
    transition: str = "cut",
    transition_duration: float = 0.4
) -> dict:
    """
    Render scenes with configurable camera motion and transitions.

    Motion:
        none      - Original framing
        zoom_in   - Gradual zoom towards centre
        zoom_out  - Gradual zoom away from centre
        pan       - Gradual horizontal pan

    Transitions:
        cut       - Direct scene changes
        crossfade - Blend adjacent scenes
        fadeblack - Fade out, brief black, fade in
    """

    scenes = timeline.get("scenes", [])

    if not scenes:
        raise ValueError("Timeline contains no scenes.")

    total_duration = float(timeline["total_duration"])

    if total_duration <= 0:
        raise ValueError("Invalid timeline duration.")

    if width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("Invalid output dimensions or FPS.")

    if motion not in {"none", "zoom_in", "zoom_out", "pan"}:
        raise ValueError(f"Unsupported motion: {motion}")

    if not 0 <= motion_strength <= 0.20:
        raise ValueError("Motion strength must be between 0 and 0.20.")

    if transition not in {"cut", "crossfade", "fadeblack"}:
        raise ValueError(f"Unsupported transition: {transition}")

    if transition_duration < 0:
        raise ValueError("Transition duration cannot be negative.")

    if transition != "cut" and transition_duration <= 0:
        raise ValueError("Transitions require a positive duration.")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    command = ["ffmpeg", "-y"]
    filters = []
    durations = []
    scene_motions = []

    # Prepare each scene independently.
    for index, scene in enumerate(scenes):

        asset_path = scene.get("asset_path")

        if not asset_path or not os.path.isfile(asset_path):
            raise FileNotFoundError(
                f"Video file missing for scene "
                f"{scene.get('scene_number')}: {asset_path}"
            )

        start = float(scene["start"])
        end = float(scene["end"])

        if start < 0 or end <= start or end > total_duration + 0.01:
            raise ValueError(
                f"Invalid timing for scene {scene.get('scene_number')}."
            )

        duration = end - start
        durations.append(duration)

        frame_count = max(1, round(duration * fps))

        scene_motion = scene.get("camera_motion", motion)

        if scene_motion not in {
            "none", "zoom_in", "zoom_out", "pan"
        }:
            raise ValueError(
                f"Invalid camera motion for scene "
                f"{scene.get('scene_number')}: {scene_motion}"
            )

        scene_motions.append({
            "scene_number": scene.get("scene_number"),
            "camera_motion": scene_motion
        })

        command.extend([
            "-stream_loop", "-1",
            "-i", asset_path
        ])

        # Prepare source footage at a larger resolution for camera movement.
        base_filter = (
            f"[{index}:v]"
            f"trim=duration={duration:.6f},"
            "setpts=PTS-STARTPTS,"
            f"scale={width * 2}:{height * 2}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"fps={fps},"
            "setsar=1"
        )

        if scene_motion == "zoom_in":
            increment = motion_strength / frame_count

            motion_filter = (
                f",zoompan="
                f"z='min(1+on*{increment:.10f},"
                f"1+{motion_strength:.4f})':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                f"d=1:s={width}x{height}:fps={fps}"
            )

        elif scene_motion == "zoom_out":
            decrement = motion_strength / frame_count

            motion_filter = (
                f",zoompan="
                f"z='max(1+{motion_strength:.4f}-"
                f"on*{decrement:.10f},1)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                f"d=1:s={width}x{height}:fps={fps}"
            )

        elif scene_motion == "pan":
            motion_filter = (
                f",zoompan="
                f"z='1+{motion_strength:.4f}':"
                f"x='(iw-iw/zoom)*on/{frame_count}':"
                "y='(ih-ih/zoom)/2':"
                f"d=1:s={width}x{height}:fps={fps}"
            )

        else:
            motion_filter = (
                f",scale={width}:{height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"fps={fps}"
            )

        filters.append(
            base_filter
            + motion_filter
            + ",setsar=1,format=yuv420p"
            + f"[v{index}]"
        )

    # Build the transition graph.
    if transition == "cut" or len(scenes) == 1:

        labels = "".join(
            f"[v{i}]" for i in range(len(scenes))
        )

        filters.append(
            f"{labels}concat=n={len(scenes)}:v=1:a=0[outv]"
        )

        rendered_duration = sum(durations)

    elif transition == "crossfade":

        if transition_duration >= min(durations):
            raise ValueError(
                "Transition duration must be shorter than every scene."
            )

        current_label = "v0"
        rendered_duration = durations[0]

        for index in range(1, len(scenes)):

            output_label = f"xf{index}"
            offset = rendered_duration - transition_duration

            filters.append(
                f"[{current_label}][v{index}]"
                f"xfade=transition=fade:"
                f"duration={transition_duration:.6f}:"
                f"offset={offset:.6f}"
                f"[{output_label}]"
            )

            current_label = output_label

            rendered_duration += (
                durations[index] - transition_duration
            )

        filters.append(
            f"[{current_label}]null[outv]"
        )

    elif transition == "fadeblack":

        black_interval = 0.15

        if transition_duration * 2 >= min(durations):
            raise ValueError(
                "Fade duration is too long for the scene duration."
            )

        current_label = "v0"
        rendered_duration = durations[0]

        for index in range(1, len(scenes)):

            fade_out_start = (
                rendered_duration - transition_duration
            )

            filters.append(
                f"[{current_label}]"
                f"fade=t=out:"
                f"st={fade_out_start:.6f}:"
                f"d={transition_duration:.6f}:"
                "color=black"
                f"[fadeout{index}]"
            )

            filters.append(
                f"[v{index}]"
                "fade=t=in:st=0:"
                f"d={transition_duration:.6f}:"
                "color=black"
                f"[fadein{index}]"
            )

            filters.append(
                f"color=c=black:"
                f"s={width}x{height}:"
                f"r={fps}:"
                f"d={black_interval:.6f},"
                "format=yuv420p"
                f"[black{index}]"
            )

            filters.append(
                f"[fadeout{index}]"
                f"[black{index}]"
                f"[fadein{index}]"
                "concat=n=3:v=1:a=0"
                f"[fb{index}]"
            )

            current_label = f"fb{index}"

            rendered_duration += (
                durations[index] + black_interval
            )

        filters.append(
            f"[{current_label}]null[outv]"
        )

    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
        "-an",
        "-t", f"{rendered_duration:.6f}",
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
            f"Video rendering failed:\n{error.stderr[-5000:]}"
        ) from error

    if (
        not os.path.isfile(output_path)
        or os.path.getsize(output_path) == 0
    ):
        raise RuntimeError("Rendering produced no valid output.")

    return {
        "output_path": output_path,
        "file_size": os.path.getsize(output_path),
        "scene_count": len(scenes),
        "resolution": f"{width}x{height}",
        "fps": fps,
        "duration": rendered_duration,
        "motion": motion,
        "scene_motions":scene_motions,
        "motion_strength": motion_strength,
        "transition": transition,
        "transition_duration": transition_duration
    }
