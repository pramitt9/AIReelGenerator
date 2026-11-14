
def build_timeline(scenes: list[dict], word_timestamps: dict) -> dict:
    """
    Build a scene timeline using word-level timestamps.

    Each scene occupies the time from the start of its
    narration until the next scene's narration begins.

    The final scene extends to the end of the audio.
    """

    words = word_timestamps.get("words", [])
    audio_duration = word_timestamps.get("duration")

    if not scenes:
        raise ValueError("No scenes provided.")

    if not words:
        raise ValueError("No word timestamps provided.")

    if not audio_duration or audio_duration <= 0:
        raise ValueError("Invalid audio duration.")

    ordered_scenes = sorted(
        scenes,
        key=lambda scene: scene["scene_number"]
    )

    timeline = []
    word_index = 0
    speech_segments = []

    for scene in ordered_scenes:
        narration = scene["narration"].strip()

        if not narration:
            raise ValueError(
                f"Scene {scene['scene_number']} has no narration."
            )

        expected_word_count = len(narration.split())

        matched_words = words[
            word_index:word_index + expected_word_count
        ]

        if len(matched_words) != expected_word_count:
            raise ValueError(
                f"Insufficient timestamped words for "
                f"scene {scene['scene_number']}."
            )

        speech_segments.append({
            "scene_number": scene["scene_number"],
            "narration": narration,
            "asset_path": scene["asset_path"],
            "words": matched_words,
            "start": matched_words[0]["start"],
            "speech_end": matched_words[-1]["end"],
            "camera_motion": scene.get("camera_motion", "none")
        })

        word_index += expected_word_count

    for index, segment in enumerate(speech_segments):

        start = segment["start"]

        if index + 1 < len(speech_segments):
            end = speech_segments[index + 1]["start"]
        else:
            end = audio_duration

        if end <= start:
            raise ValueError(
                f"Invalid scene timing: {segment['scene_number']}"
            )

        timeline.append({
            **segment,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3)
        })

    return {
        "total_duration": round(audio_duration, 3),
        "scene_count": len(timeline),
        "scenes": timeline
    }
