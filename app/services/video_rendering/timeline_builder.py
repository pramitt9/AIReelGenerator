
import re


def normalize_word(word: str) -> str:
    """Normalize a word for matching against Whisper output."""
    return re.sub(r"[^\w']", "", word.lower())


def match_narration_words(
    narration: str,
    whisper_words: list,
    start_index: int,
    scene_number: int
) -> tuple:
    """
    Match narration tokens against Whisper's timestamped words.

    Returns the matched timestamp words and the next unused index.
    """

    expected_words = [
        normalize_word(word)
        for word in narration.split()
        if normalize_word(word)
    ]

    if not expected_words:
        raise ValueError(
            f"Scene {scene_number} contains no usable narration words."
        )

    matched_words = []
    whisper_index = start_index

    for expected in expected_words:
        found = False

        while whisper_index < len(whisper_words):
            candidate = whisper_words[whisper_index]
            actual = normalize_word(candidate.get("word", ""))

            whisper_index += 1

            if not actual:
                continue

            # Exact match
            if actual == expected:
                matched_words.append(candidate)
                found = True
                break

            # Allow punctuation differences.
            # Do not silently skip a different spoken word.
            raise ValueError(
                f"Word alignment failed in scene {scene_number}. "
                f"Expected '{expected}', but Whisper detected '{actual}'."
            )

        if not found:
            raise ValueError(
                f"Could not align narration word '{expected}' "
                f"in scene {scene_number}."
            )

    return matched_words, whisper_index


def build_timeline(
    scenes: list,
    word_timestamps: dict,
    hook: str = "",
    ending: str = ""
) -> dict:
    """
    Build a video timeline from scene narration and Whisper timestamps.

    The opening hook is assigned to the first scene.
    The ending is assigned to the last scene.

    Scene boundaries are based on the first spoken word of each
    scene, and the final scene ends at the audio duration.
    """

    if not scenes:
        raise ValueError("Cannot build a timeline without scenes.")

    if not isinstance(word_timestamps, dict):
        raise ValueError("Invalid word timestamp data.")

    words = word_timestamps.get("words", [])
    audio_duration = word_timestamps.get("duration")

    if not words:
        raise ValueError("No word timestamps were provided.")

    if not isinstance(audio_duration, (int, float)) or audio_duration <= 0:
        raise ValueError("Invalid audio duration.")

    ordered_scenes = sorted(
        scenes,
        key=lambda scene: scene["scene_number"]
    )

    if len(ordered_scenes) != len(scenes):
        raise ValueError("Invalid scene data.")

    speech_segments = []
    word_index = 0

    # Match hook words before the first scene narration.
    if hook and hook.strip():
        hook_words, word_index = match_narration_words(
            hook.strip(),
            words,
            word_index,
            scene_number=ordered_scenes[0]["scene_number"]
        )
    else:
        hook_words = []

    # Match each scene's narration.
    for scene in ordered_scenes:
        scene_number = scene["scene_number"]
        narration = scene["narration"].strip()

        if not narration:
            raise ValueError(
                f"Scene {scene_number} has empty narration."
            )

        matched_words, word_index = match_narration_words(
            narration,
            words,
            word_index,
            scene_number
        )

        speech_segments.append({
            "scene_number": scene_number,
            "narration": narration,
            "asset_path": scene["asset_path"],
            "camera_motion": scene.get("camera_motion", "none"),
            "words": matched_words,
            "start": matched_words[0]["start"],
            "speech_end": matched_words[-1]["end"]
        })

    # Match ending words after the last scene narration.
    if ending and ending.strip():
        ending_words, word_index = match_narration_words(
            ending.strip(),
            words,
            word_index,
            scene_number=ordered_scenes[-1]["scene_number"]
        )
    else:
        ending_words = []

    # The first scene starts at zero so the hook is not cut off.
    if hook_words:
        speech_segments[0]["start"] = hook_words[0]["start"]
        speech_segments[0]["words"] = (
            hook_words + speech_segments[0]["words"]
        )

    # The last scene includes the ending.
    if ending_words:
        speech_segments[-1]["words"].extend(ending_words)
        speech_segments[-1]["speech_end"] = ending_words[-1]["end"]

    # Reject unexpected remaining speech.
    if word_index < len(words):
        remaining = words[word_index:]

        # Whisper can occasionally produce trailing empty tokens.
        remaining = [
            word for word in remaining
            if normalize_word(word.get("word", ""))
        ]

        if remaining:
            raise ValueError(
                "Some spoken words could not be assigned to a scene. "
                f"First unassigned word: '{remaining[0].get('word', '')}'."
            )

    # Construct scene boundaries.
    timeline = []

    for index, segment in enumerate(speech_segments):
        start = 0.0 if index == 0 else segment["start"]

        if index < len(speech_segments) - 1:
            end = speech_segments[index + 1]["start"]
        else:
            end = float(audio_duration)

        if end <= start:
            raise ValueError(
                f"Invalid timeline duration for scene "
                f"{segment['scene_number']}."
            )

        timeline.append({
            **segment,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3)
        })

    total_duration = round(float(audio_duration), 3)

    return {
        "total_duration": total_duration,
        "scene_count": len(timeline),
        "scenes": timeline
    }
