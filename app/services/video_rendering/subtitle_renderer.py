
import os
import subprocess


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
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
    )


def create_caption_groups(words: list[dict]) -> list[list[dict]]:
    """
    Group words into readable caption chunks.

    Break after punctuation, long pauses, or a maximum
    number of words/characters.
    """

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
    """Generate an ASS subtitle file with animated word highlighting."""

    if not words:
        raise ValueError("No word timestamps provided.")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    groups = create_caption_groups(words)

    header = """[Script Info]
Title: AI Reel Generator Captions
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

            clean_word = escape_ass_text(word["word"])

            karaoke_text.append(
                f"{{\\kf{duration}}}{clean_word}"
            )

        text = " ".join(karaoke_text)

        dialogue_lines.append(
            f"Dialogue: 0,"
            f"{format_ass_time(start)},"
            f"{format_ass_time(end)},"
            f"Default,,0,0,0,,{text}"
        )

    with open(output_path, "w", encoding="utf-8-sig") as file:
        file.write(header)
        file.write("\n".join(dialogue_lines))

    return {
        "subtitle_path": output_path,
        "caption_groups": len(groups),
        "word_count": len(words)
    }



def render_subtitles(
    video_path: str,
    audio_path: str,
    words: list[dict],
    output_path: str,
    subtitle_path: str = None
) -> dict:
    """Burn synchronized captions into video and add the final audio."""

    for path, label in [
        (video_path, "Video"),
        (audio_path, "Audio")
    ]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{label} not found: {path}")

    if subtitle_path is None:
        subtitle_path = os.path.splitext(output_path)[0] + ".ass"

    subtitle_result = generate_ass_subtitles(words, subtitle_path)

    escaped_path = os.path.abspath(subtitle_path)
    escaped_path = escaped_path.replace("\\", "/")
    escaped_path = escaped_path.replace(":", r"\:")
    escaped_path = escaped_path.replace("'", r"\'")

    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", f"ass='{escaped_path}'",
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
            f"Subtitle rendering failed:\n{error.stderr[-4000:]}"
        ) from error

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Subtitle rendering produced no output.")

    return {
        "output_path": output_path,
        "file_size": os.path.getsize(output_path),
        "word_count": subtitle_result["word_count"],
        "caption_groups": subtitle_result["caption_groups"],
        "subtitle_path": subtitle_path
    }

