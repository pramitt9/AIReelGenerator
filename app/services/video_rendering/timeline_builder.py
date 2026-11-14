
import math
import re
from difflib import SequenceMatcher


def normalize_word(word: str) -> str:
    """Normalize a word for narration alignment."""
    if not isinstance(word, str):
        return ""

    return re.sub(r"[^\w']", "", word.lower())


def tokenize(text: str) -> list[str]:
    """Convert narration into normalized word tokens."""
    if not isinstance(text, str):
        return []

    return [
        normalized
        for word in text.split()
        if (normalized := normalize_word(word))
    ]


def align_words(
    expected_words: list[str],
    whisper_words: list[dict]
) -> list[tuple[int, int]]:
    """
    Align expected narration tokens with Whisper timestamps.

    Only exact or sufficiently similar word pairs are returned.
    Missing and extra words are tolerated within the mismatch limit.
    """

    if not expected_words or not whisper_words:
        raise ValueError("Cannot align empty narration or transcription.")

    actual_words = [
        normalize_word(word.get("word", ""))
        for word in whisper_words
    ]

    n = len(expected_words)
    m = len(actual_words)

    # Dynamic programming edit-distance alignment.
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    trace = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = float(i)
        trace[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = float(j)
        trace[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            expected = expected_words[i - 1]
            actual = actual_words[j - 1]

            if expected == actual:
                substitution_cost = 0.0
            else:
                similarity = SequenceMatcher(
                    None, expected, actual
                ).ratio()

                substitution_cost = (
                    0.5 if similarity >= 0.80 else 1.0
                )

            choices = [
                (dp[i - 1][j - 1] + substitution_cost, "substitute"),
                (dp[i - 1][j] + 1.0, "delete"),
                (dp[i][j - 1] + 1.0, "insert")
            ]

            dp[i][j], trace[i][j] = min(
                choices,
                key=lambda item: item[0]
            )

    # Reconstruct the alignment.
    pairs = []
    i, j = n, m

    while i > 0 or j > 0:
        operation = trace[i][j]

        if operation == "substitute":
            expected = expected_words[i - 1]
            actual = actual_words[j - 1]

            similarity = SequenceMatcher(
                None, expected, actual
            ).ratio()

            # Do not assign unrelated words to narration scenes.
            if expected == actual or similarity >= 0.80:
                pairs.append((i - 1, j - 1))

            i -= 1
            j -= 1

        elif operation == "delete":
            i -= 1

        elif operation == "insert":
            j -= 1

        else:
            raise ValueError("Could not reconstruct word alignment.")

    pairs.reverse()

    error_ratio = dp[n][m] / max(n, m)

    if error_ratio > 0.30:
        raise ValueError(
            "Narration alignment is unreliable. "
            f"Transcription mismatch: {error_ratio:.0%}. "
            "Check the generated narration and Whisper transcription."
        )

    if not pairs:
        raise ValueError(
            "No reliable word matches were found between narration "
            "and transcription."
        )

    return pairs


def _validate_scenes(scenes: list) -> list:
    """Validate and sort storyboard scenes."""
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Cannot build a timeline without scenes.")

    validated = []
    scene_numbers = set()

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Invalid scene data at position {index}.")

        scene_number = scene.get("scene_number")

        if (
            not isinstance(scene_number, int)
            or isinstance(scene_number, bool)
            or scene_number < 1
        ):
            raise ValueError(
                f"Invalid scene number at position {index}."
            )

        if scene_number in scene_numbers:
            raise ValueError(
                f"Duplicate scene number: {scene_number}."
            )

        scene_numbers.add(scene_number)

        narration = scene.get("narration")
        asset_path = scene.get("asset_path")

        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(
                f"Scene {scene_number} has empty narration."
            )

        if not isinstance(asset_path, str) or not asset_path.strip():
            raise ValueError(
                f"Scene {scene_number} has no video asset."
            )

        validated.append(scene)

    return sorted(validated, key=lambda scene: scene["scene_number"])


def _validate_word_timestamps(words: list, audio_duration: float) -> list:
    """Validate Whisper timestamps and preserve original word records."""
    if not isinstance(words, list) or not words:
        raise ValueError("No word timestamps were provided.")

    valid_words = []
    previous_start = -1.0

    for index, word in enumerate(words, start=1):
        if not isinstance(word, dict):
            raise ValueError(
                f"Invalid Whisper word record at position {index}."
            )

        normalized = normalize_word(word.get("word", ""))

        if not normalized:
            continue

        try:
            start = float(word["start"])
            end = float(word["end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"Invalid timestamps for Whisper word at position {index}."
            )

        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError(
                f"Non-finite timestamps for Whisper word at position {index}."
            )

        if start < 0 or end <= start:
            raise ValueError(
                f"Invalid time range for Whisper word: {word.get('word')}."
            )

        if end > audio_duration + 0.5:
            raise ValueError(
                f"Whisper word exceeds audio duration: {word.get('word')}."
            )

        if start < previous_start:
            raise ValueError(
                "Whisper word timestamps are not in chronological order."
            )

        previous_start = start
        valid_words.append(word)

    if not valid_words:
        raise ValueError("No valid Whisper word timestamps were found.")

    return valid_words


def build_timeline(
    scenes: list,
    word_timestamps: dict,
    hook: str = "",
    ending: str = ""
) -> dict:
    """
    Build a scene timeline using aligned Whisper timestamps.

    Hook words belong to the first scene.
    Ending words belong to the last scene.
    Original Whisper records are preserved for subtitle rendering.
    """

    ordered_scenes = _validate_scenes(scenes)

    if not isinstance(word_timestamps, dict):
        raise ValueError("Invalid word timestamp data.")

    try:
        audio_duration = float(word_timestamps.get("duration"))
    except (TypeError, ValueError):
        raise ValueError("Invalid audio duration.")

    if not math.isfinite(audio_duration) or audio_duration <= 0:
        raise ValueError("Invalid audio duration.")

    words = _validate_word_timestamps(
        word_timestamps.get("words"),
        audio_duration
    )

    # Build the complete expected narration sequence.
    expected_words = []
    word_owners = []

    for scene_index, scene in enumerate(ordered_scenes):
        if scene_index == 0 and isinstance(hook, str) and hook.strip():
            hook_tokens = tokenize(hook)
            expected_words.extend(hook_tokens)
            word_owners.extend([0] * len(hook_tokens))

        scene_tokens = tokenize(scene["narration"])

        if not scene_tokens:
            raise ValueError(
                f"Scene {scene['scene_number']} has no usable narration words."
            )

        expected_words.extend(scene_tokens)
        word_owners.extend([scene_index] * len(scene_tokens))

    if isinstance(ending, str) and ending.strip():
        ending_tokens = tokenize(ending)
        expected_words.extend(ending_tokens)
        word_owners.extend(
            [len(ordered_scenes) - 1] * len(ending_tokens)
        )

    if not expected_words:
        raise ValueError("No usable narration words were found.")

    # Align the narration with Whisper's transcription.
    alignment = align_words(expected_words, words)

    scene_words = [[] for _ in ordered_scenes]

    whisper_owner = {}

    for expected_index, whisper_index in alignment:
        owner = word_owners[expected_index]
        scene_words[owner].append(words[whisper_index])
        whisper_owner[whisper_index] = owner

    # Assign unmatched transcription words to the nearest preceding
    # matched scene. Words before the first match belong to scene one.
    last_owner = 0

    for whisper_index, word in enumerate(words):
        if whisper_index in whisper_owner:
            last_owner = whisper_owner[whisper_index]
            continue

        scene_words[last_owner].append(word)

    for assigned_words in scene_words:
        assigned_words.sort(key=lambda word: float(word["start"]))

    # Every scene must have at least one matched or assigned word.
    for index, assigned_words in enumerate(scene_words):
        if not assigned_words:
            scene_number = ordered_scenes[index]["scene_number"]
            raise ValueError(
                f"Could not assign any audio words to scene {scene_number}."
            )

    # Calculate scene boundaries. When there is a pause between scenes,
    # split the pause at its midpoint. Otherwise, use the next scene's
    # first spoken word as the boundary.
    boundaries = [0.0]

    for index in range(len(ordered_scenes) - 1):
        previous_end = float(scene_words[index][-1]["end"])
        next_start = float(scene_words[index + 1][0]["start"])

        if next_start > previous_end:
            boundary = (previous_end + next_start) / 2.0
        else:
            boundary = next_start

        boundary = max(boundaries[-1], boundary)
        boundary = min(boundary, audio_duration)

        boundaries.append(boundary)

    boundaries.append(audio_duration)

    timeline = []

    for index, scene in enumerate(ordered_scenes):
        assigned_words = scene_words[index]

        start = boundaries[index]
        end = boundaries[index + 1]

        if end <= start:
            raise ValueError(
                f"Invalid timeline duration for scene "
                f"{scene['scene_number']}."
            )

        speech_end = max(
            float(word["end"]) for word in assigned_words
        )

        timeline.append({
            "scene_number": scene["scene_number"],
            "narration": scene["narration"],
            "asset_path": scene["asset_path"],
            "camera_motion": scene.get("camera_motion", "none"),
            "words": assigned_words,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "speech_end": round(speech_end, 3)
        })

    return {
        "total_duration": round(audio_duration, 3),
        "scene_count": len(timeline),
        "scenes": timeline
    }
