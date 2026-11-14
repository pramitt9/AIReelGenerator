
import re
from difflib import SequenceMatcher


def normalize_word(word: str) -> str:
    """Normalize words for narration alignment."""
    return re.sub(r"[^\w']", "", word.lower())


def tokenize(text: str) -> list[str]:
    """Convert narration into normalized word tokens."""
    return [
        normalized
        for word in text.split()
        if (normalized := normalize_word(word))
    ]


def align_words(expected_words: list[str], whisper_words: list[dict]) -> list[tuple]:
    """
    Align expected narration tokens with Whisper's timestamped words.

    Returns pairs of (expected_index, whisper_index).
    Missing and extra words are tolerated, while original Whisper
    records and timestamps remain unchanged.
    """

    actual_words = [
        normalize_word(word.get("word", ""))
        for word in whisper_words
    ]

    n = len(expected_words)
    m = len(actual_words)

    if not n or not m:
        raise ValueError("Cannot align empty narration or transcription.")

    # Dynamic programming edit-distance alignment.
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        trace[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = j
        trace[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            expected = expected_words[i - 1]
            actual = actual_words[j - 1]

            if expected == actual:
                substitution_cost = 0
            else:
                similarity = SequenceMatcher(
                    None, expected, actual
                ).ratio()

                substitution_cost = (
                    0.5 if similarity >= 0.75 else 1.0
                )

            choices = [
                (dp[i - 1][j - 1] + substitution_cost, "match"),
                (dp[i - 1][j] + 1, "delete"),
                (dp[i][j - 1] + 1, "insert")
            ]

            dp[i][j], trace[i][j] = min(
                choices,
                key=lambda item: item[0]
            )

    # Trace the alignment backwards.
    pairs = []
    i, j = n, m

    while i > 0 or j > 0:
        operation = trace[i][j]

        if operation == "match":
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

    # Reject transcriptions that differ too substantially.
    error_ratio = dp[n][m] / max(n, m)

    if error_ratio > 0.30:
        raise ValueError(
            "Narration alignment is unreliable. "
            f"Transcription mismatch: {error_ratio:.0%}. "
            "Check the generated narration and Whisper transcription."
        )

    return pairs


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
    Original Whisper word records are preserved for subtitles.
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

    # Build one continuous expected narration sequence.
    expected_words = []
    word_owners = []

    for scene_index, scene in enumerate(ordered_scenes):
        narration = scene.get("narration", "").strip()

        if not narration:
            raise ValueError(
                f"Scene {scene['scene_number']} has empty narration."
            )

        if scene_index == 0 and hook and hook.strip():
            hook_tokens = tokenize(hook)

            expected_words.extend(hook_tokens)
            word_owners.extend([0] * len(hook_tokens))

        scene_tokens = tokenize(narration)

        expected_words.extend(scene_tokens)
        word_owners.extend([scene_index] * len(scene_tokens))

    if ending and ending.strip():
        ending_tokens = tokenize(ending)

        expected_words.extend(ending_tokens)
        word_owners.extend(
            [len(ordered_scenes) - 1] * len(ending_tokens)
        )

    if not expected_words:
        raise ValueError("No usable narration words were found.")

    # Validate and clean Whisper records without changing their contents.
    valid_words = []

    for word in words:
        normalized = normalize_word(word.get("word", ""))

        if not normalized:
            continue

        try:
            start = float(word["start"])
            end = float(word["end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid Whisper word timestamps.")

        if start < 0 or end <= start or end > audio_duration + 0.5:
            raise ValueError(
                f"Invalid timestamp for Whisper word: {word.get('word')}"
            )

        valid_words.append(word)

    if not valid_words:
        raise ValueError("No valid Whisper word timestamps were found.")

    # Align the complete narration.
    alignment = align_words(expected_words, valid_words)

    # Assign original Whisper records to their corresponding scenes.
    scene_words = [[] for _ in ordered_scenes]

    for expected_index, whisper_index in alignment:
        owner = word_owners[expected_index]
        scene_words[owner].append(valid_words[whisper_index])

    # Assign unmatched extra Whisper words to the nearest preceding scene.
    matched_indices = {
        whisper_index
        for _, whisper_index in alignment
    }

    whisper_owner = {
        whisper_index: word_owners[expected_index]
        for expected_index, whisper_index in alignment
    }

    for whisper_index, word in enumerate(valid_words):
        if whisper_index in matched_indices:
            continue

        previous_matches = [
            index for index in whisper_owner
            if index < whisper_index
        ]

        if previous_matches:
            owner = whisper_owner[max(previous_matches)]
        else:
            owner = 0

        scene_words[owner].append(word)

    # Sort words by their original audio timestamps.
    for assigned_words in scene_words:
        assigned_words.sort(key=lambda word: word["start"])

    # Every scene must have at least one timestamped word.
    for index, assigned_words in enumerate(scene_words):
        if not assigned_words:
            raise ValueError(
                f"Could not assign any audio words to scene "
                f"{ordered_scenes[index]['scene_number']}."
            )

    # Construct scene boundaries.
    timeline = []

    for index, scene in enumerate(ordered_scenes):
        assigned_words = scene_words[index]

        start = (
            0.0
            if index == 0
            else float(assigned_words[0]["start"])
        )

        if index < len(ordered_scenes) - 1:
            end = float(scene_words[index + 1][0]["start"])
        else:
            end = float(audio_duration)

        if end <= start:
            raise ValueError(
                f"Invalid timeline duration for scene "
                f"{scene['scene_number']}."
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
            "speech_end": round(
                float(assigned_words[-1]["end"]), 3
            )
        })

    return {
        "total_duration": round(float(audio_duration), 3),
        "scene_count": len(timeline),
        "scenes": timeline
    }
