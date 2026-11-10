
import re


def calculate_score(video: dict, query: str, target_duration: int = 5) -> float:
    """Score a video for a particular storyboard scene."""

    score = 0.0

    width = video.get("width") or 0
    height = video.get("height") or 0
    duration = video.get("duration") or 0

    # 1. Orientation: portrait is ideal for Reels.
    if width and height:
        ratio = width / height

        if 0.52 <= ratio <= 0.62:
            score += 35
        elif 0.9 <= ratio <= 1.1:
            score += 25
        elif ratio > 1.1:
            score += 15

    # 2. Resolution.
    if width >= 1080 and height >= 1920:
        score += 25
    elif width >= 1920 and height >= 1080:
        score += 20
    elif width >= 720 and height >= 720:
        score += 10

    # 3. Duration suitability.
    if duration:
        difference = abs(duration - target_duration)
        score += max(0, 20 - difference * 3)

    # 4. Basic keyword relevance from Pixabay tags.
    query_words = set(re.findall(r"\w+", query.lower()))
    tag_words = set(
        re.findall(r"\w+", (video.get("tags") or "").lower())
    )

    if query_words:
        overlap = len(query_words & tag_words)
        score += min(20, overlap * 5)

    return round(score, 2)


def select_best_video(
    videos: list,
    query: str,
    target_duration: int = 5
):
    """Return the highest-scoring video, or None."""

    if not videos:
        return None

    ranked = sorted(
        videos,
        key=lambda video: calculate_score(
            video, query, target_duration
        ),
        reverse=True
    )

    return ranked[0]


def rank_videos(
    videos: list,
    query: str,
    target_duration: int = 5
):
    """Return all videos ranked from best to worst."""

    return sorted(
        videos,
        key=lambda video: calculate_score(
            video, query, target_duration
        ),
        reverse=True
    )
