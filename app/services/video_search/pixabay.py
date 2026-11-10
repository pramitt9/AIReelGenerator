
import requests
from flask import current_app


PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"


def search_videos(query: str, per_page: int = 10) -> list:
    """
    Search Pixabay for videos matching a scene description.
    Returns normalized video metadata.
    """

    api_key = current_app.config.get("PIXABAY_API_KEY")

    if not api_key:
        raise ValueError("Pixabay API key is not configured.")

    params = {
        "key": api_key,
        "q": query,
        "per_page": min(per_page, 20),
        "safesearch": "true"
    }

    try:
        response = requests.get(
            PIXABAY_VIDEO_URL,
            params=params,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException as exc:
        raise RuntimeError("Pixabay video search failed.") from exc

    results = []

    for video in data.get("hits", []):
        videos = video.get("videos", {})

        # Prefer larger versions, falling back when unavailable.
        selected = (
            videos.get("large")
            or videos.get("medium")
            or videos.get("small")
        )

        if not selected:
            continue

        results.append({
            "provider": "pixabay",
            "video_id": video.get("id"),
            "url": selected.get("url"),
            "thumbnail": video.get("userImageURL"),
            "width": selected.get("width"),
            "height": selected.get("height"),
            "duration": video.get("duration"),
            "tags": video.get("tags"),
            "views": video.get("views"),
            "user": video.get("user")
        })

    return results
