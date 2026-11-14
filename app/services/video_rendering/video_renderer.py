
import os
import subprocess
import uuid
import math
from fractions import Fraction
from pathlib import Path


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

    Supports:
        none      - Original framing
        zoom_in   - Gradual zoom towards centre
        zoom_out  - Gradual zoom away from centre
        pan       - Gradual horizontal pan

    Transitions:
        cut       - Direct scene changes
        crossfade - Blend adjacent scenes
        fadeblack - Fade out, brief black, fade in

    Renders to a temporary file and replaces the destination
    only after successful FFprobe validation.
    """

    if not isinstance(timeline, dict):
        raise ValueError("Timeline must be a dictionary.")

    scenes = timeline.get("scenes", [])

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Timeline contains no scenes.")

    total_duration = float(timeline["total_duration"])

    if not math.isfinite(total_duration) or total_duration <= 0:
        raise ValueError("Invalid timeline duration.")

    if width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("Invalid output dimensions or FPS.")

    if motion not in {"none", "zoom_in", "zoom_out", "pan"}:
        raise ValueError(f"Unsupported motion: {motion}")

    if not 0 <= motion_strength <= 0.20:
        raise ValueError("Motion strength must be between 0 and 0.20.")

    if transition not in {"cut", "crossfade", "fadeblack"}:
        raise ValueError(f"Unsupported transition: {transition}")

    if not math.isfinite(transition_duration) or transition_duration < 0:
        raise ValueError("Transition duration cannot be negative.")

    if transition != "cut" and transition_duration <= 0:
        raise ValueError("Transitions require a positive duration.")

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_output = output.with_name(
        f"{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix}"
    )

    command = ["ffmpeg", "-y"]
    filters = []
    durations = []
    scene_motions = []

    try:
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

            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError(
                    f"Non-finite timing for scene {scene.get('scene_number')}."
                )

            if (
                start < 0
                or end <= start
                or end > total_duration + 0.01
            ):
                raise ValueError(
                    f"Invalid timing for scene "
                    f"{scene.get('scene_number')}."
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
                "-i", str(Path(asset_path).resolve())
            ])

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
                    ",zoompan="
                    f"z='min(1+on*{increment:.10f},"
                    f"1+{motion_strength:.4f})':"
                    "x='iw/2-(iw/zoom/2)':"
                    "y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={width}x{height}:fps={fps}"
                )

            elif scene_motion == "zoom_out":
                decrement = motion_strength / frame_count

                motion_filter = (
                    ",zoompan="
                    f"z='max(1+{motion_strength:.4f}-"
                    f"on*{decrement:.10f},1)':"
                    "x='iw/2-(iw/zoom/2)':"
                    "y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={width}x{height}:fps={fps}"
                )

            elif scene_motion == "pan":
                motion_filter = (
                    ",zoompan="
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

        # Render to a unique temporary file.
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
            str(temporary_output)
        ])

        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        if (
            not temporary_output.is_file()
            or temporary_output.stat().st_size == 0
        ):
            raise RuntimeError(
                "Rendering produced an empty output file."
            )

        # Validate the temporary video using FFprobe.
        probe_command = [
            "ffprobe",
            "-v", "error",
            "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate,r_frame_rate,duration,nb_frames:format=duration",
            "-of", "json",
            str(temporary_output)
        ]

        probe_result = subprocess.run(
            probe_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        import json

        probe_data = json.loads(probe_result.stdout)

        video_streams = [
            stream
            for stream in probe_data.get("streams", [])
            if stream.get("codec_type") == "video"
        ]

        if len(video_streams) != 1:
            raise RuntimeError(
                "Rendered file must contain exactly one video stream."
            )

        video_stream = video_streams[0]

        if (
            video_stream.get("width") != width
            or video_stream.get("height") != height
        ):
            raise RuntimeError(
                "Rendered video has an unexpected resolution."
            )

        actual_duration = float(
            probe_data.get("format", {}).get("duration", 0)
        )

        if not math.isfinite(actual_duration) or actual_duration <= 0:
            raise RuntimeError(
                "Rendered video has an invalid duration."
            )

        # Verify that FFmpeg produced the intended frame rate.
        reported_fps = (
            video_stream.get("avg_frame_rate")
            or video_stream.get("r_frame_rate")
        )
        try:
            actual_fps = float(Fraction(reported_fps))
        except (TypeError, ValueError, ZeroDivisionError):
            raise RuntimeError(
                "FFprobe could not determine the rendered frame rate."
            )

        if not math.isfinite(actual_fps) or abs(actual_fps - fps) > 0.05:
            raise RuntimeError(
                f"Rendered video has an unexpected frame rate: "
                f"{actual_fps:g} FPS (expected {fps} FPS)."
            )

        # Duration can differ by a small number of encoded frames.
        duration_tolerance = max(0.15, 2.0 / fps)
        if abs(actual_duration - rendered_duration) > duration_tolerance:
            raise RuntimeError(
                f"Rendered duration mismatch: {actual_duration:.3f}s "
                f"(expected {rendered_duration:.3f}s, tolerance "
                f"{duration_tolerance:.3f}s)."
            )

        # Replace the destination only after every validation succeeds.
        os.replace(temporary_output, output)

        return {
            "output_path": str(output),
            "file_size": output.stat().st_size,
            "scene_count": len(scenes),
            "resolution": f"{width}x{height}",
            "fps": fps,
            "duration": actual_duration,
            "motion": motion,
            "scene_motions": scene_motions,
            "motion_strength": motion_strength,
            "transition": transition,
            "transition_duration": transition_duration
        }

    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg or a required input file was not found. "
            "Check that FFmpeg is installed and all scene assets exist."
        ) from error

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Video rendering or validation failed:\n"
            f"{error.stderr[-5000:]}"
        ) from error

    finally:
        temporary_output.unlink(missing_ok=True)
