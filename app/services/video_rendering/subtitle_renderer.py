import json
import math
import os
import subprocess
import uuid
from pathlib import Path


def format_ass_time(seconds: float) -> str:
    """Convert seconds into ASS timestamp format: H:MM:SS.cc."""
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    """Escape special ASS text characters."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _validated_words(words: list[dict]) -> list[dict]:
    if not isinstance(words, list) or not words:
        raise ValueError("No word timestamps provided.")

    validated = []
    previous_start = -1.0

    for index, item in enumerate(words):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid word timestamp at index {index}.")

        try:
            start = float(item["start"])
            end = float(item["end"])
            word = str(item["word"]).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid word timestamp data at index {index}."
            ) from error

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
            or start < previous_start
            or not word
        ):
            raise ValueError(
                f"Invalid or out-of-order word timing at index {index}."
            )

        validated.append({
            **item,
            "start": start,
            "end": end,
            "word": word,
        })
        previous_start = start

    return validated


def create_caption_groups(words: list[dict]) -> list[list[dict]]:
    """Group words into readable caption chunks."""
    words = _validated_words(words)
    groups = []
    current_group = []

    for word in words:
        if current_group:
            previous = current_group[-1]
            gap = word["start"] - previous["end"]
            current_text = " ".join(
                item["word"] for item in current_group
            )
            should_break = (
                gap > 0.65
                or len(current_group) >= 5
                or len(current_text) + len(word["word"]) + 1 > 32
                or previous["word"].endswith((".", "?", "!"))
            )
            if should_break:
                groups.append(current_group)
                current_group = []

        current_group.append(word)

    if current_group:
        groups.append(current_group)

    return groups


def generate_ass_subtitles(
    words: list[dict],
    output_path: str
) -> dict:
    """Generate ASS subtitles with animated word highlighting."""
    words = _validated_words(words)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    groups = create_caption_groups(words)

    header = """[Script Info]
Title: VidSnapAI Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,66,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []
    for group in groups:
        start = group[0]["start"]
        end = group[-1]["end"]
        karaoke_text = []

        for word in group:
            duration = max(
                1,
                round((word["end"] - word["start"]) * 100)
            )
            karaoke_text.append(
                f"{{\\kf{duration}}}{escape_ass_text(word['word'])}"
            )

        dialogue_lines.append(
            f"Dialogue: 0,{format_ass_time(start)},"
            f"{format_ass_time(end)},Default,,0,0,0,,"
            + " ".join(karaoke_text)
        )

    with open(output, "w", encoding="utf-8-sig", newline="\n") as file:
        file.write(header)
        file.write("\n".join(dialogue_lines))
        file.write("\n")

    return {
        "subtitle_path": str(output),
        "caption_groups": len(groups),
        "word_count": len(words),
    }


def _probe_media(path: str) -> dict:
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "stream=codec_type,width,height,duration:format=duration",
        "-of", "json",
        str(Path(path).resolve()),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    duration = float(data.get("format", {}).get("duration", 0) or 0)

    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"Media has an invalid duration: {path}")

    return {"streams": streams, "duration": duration}


def render_subtitles(
    video_path: str,
    audio_path: str,
    words: list[dict],
    output_path: str,
    subtitle_path: str = None
) -> dict:
    """
    Burn synchronized captions into video and add final audio.

    The output duration follows the silent video. Audio is padded if it ends
    slightly early and trimmed if it extends beyond the video. The output
    is replaced only after FFprobe validation succeeds.
    """
    for path, label in [
        (video_path, "Video"),
        (audio_path, "Audio"),
    ]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{label} not found: {path}")

    words = _validated_words(words)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if subtitle_path is None:
        subtitle_path = str(output.parent / f"{output.stem}.ass")

    subtitle_file = Path(subtitle_path).resolve()
    temporary_output = output.with_name(
        f"{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix}"
    )

    try:
        video_info = _probe_media(video_path)
        audio_info = _probe_media(audio_path)

        video_streams = [
            stream for stream in video_info["streams"]
            if stream.get("codec_type") == "video"
        ]
        audio_streams = [
            stream for stream in audio_info["streams"]
            if stream.get("codec_type") == "audio"
        ]
        if not video_streams:
            raise RuntimeError("Input file does not contain a video stream.")
        if not audio_streams:
            raise RuntimeError("Narration file does not contain an audio stream.")

        video_duration = video_info["duration"]
        audio_duration = audio_info["duration"]

        if words[-1]["end"] > video_duration + 0.25:
            raise ValueError(
                "Subtitle timestamps extend beyond the video duration."
            )
        if words[-1]["end"] > audio_duration + 0.50:
            raise ValueError(
                "Subtitle timestamps extend beyond the narration duration."
            )

        subtitle_result = generate_ass_subtitles(
            words,
            str(subtitle_file)
        )

        escaped_path = str(subtitle_file).replace("\\", "/")
        escaped_path = escaped_path.replace(":", r"\:")
        escaped_path = escaped_path.replace("'", r"\'")

        command = [
            "ffmpeg",
            "-y",
            "-i", str(Path(video_path).resolve()),
            "-i", str(Path(audio_path).resolve()),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", f"ass='{escaped_path}'",
            "-af", "apad",
            "-t", f"{video_duration:.6f}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(temporary_output),
        ]

        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        if (
            not temporary_output.is_file()
            or temporary_output.stat().st_size == 0
        ):
            raise RuntimeError(
                "Subtitle rendering produced an empty output."
            )

        final_info = _probe_media(str(temporary_output))
        final_streams = final_info["streams"]
        final_video_streams = [
            stream for stream in final_streams
            if stream.get("codec_type") == "video"
        ]
        final_audio_streams = [
            stream for stream in final_streams
            if stream.get("codec_type") == "audio"
        ]

        if len(final_video_streams) != 1 or len(final_audio_streams) != 1:
            raise RuntimeError(
                "Final video must contain exactly one video and one audio stream."
            )

        final_duration = final_info["duration"]
        if abs(final_duration - video_duration) > 0.35:
            raise RuntimeError(
                "Final video duration does not match the rendered video. "
                f"Expected {video_duration:.3f}s, got {final_duration:.3f}s."
            )

        expected_width = video_streams[0].get("width")
        expected_height = video_streams[0].get("height")
        final_video = final_video_streams[0]
        if (
            final_video.get("width") != expected_width
            or final_video.get("height") != expected_height
        ):
            raise RuntimeError(
                "Final video resolution changed during subtitle rendering."
            )

        os.replace(temporary_output, output)

    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg, FFprobe, or a required media file was not found. "
            "Check that FFmpeg and FFprobe are installed and available in PATH."
        ) from error

    except subprocess.CalledProcessError as error:
        details = error.stderr or str(error)
        raise RuntimeError(
            f"Subtitle rendering or media validation failed:\n{details[-4000:]}"
        ) from error

    finally:
        temporary_output.unlink(missing_ok=True)

    return {
        "output_path": str(output),
        "file_size": output.stat().st_size,
        "word_count": subtitle_result["word_count"],
        "caption_groups": subtitle_result["caption_groups"],
        "subtitle_path": str(subtitle_file),
        "duration": final_duration,
    }
