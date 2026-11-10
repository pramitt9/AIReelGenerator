
from app import create_app
from app.services.video_search.pixabay import search_videos
from app.services.video_search.asset_selector import (
    rank_videos,
    select_best_video,
    calculate_score
)

app = create_app()

with app.app_context():

    query = "futuristic technology city"

    videos = search_videos(query, per_page=10)

    ranked = rank_videos(
        videos,
        query,
        target_duration=5
    )

    print("\n===== RANKED FOOTAGE =====")

    for video in ranked:
        score = calculate_score(video, query, 5)

        print(
            f"ID: {video['video_id']} | "
            f"Resolution: {video['width']}x{video['height']} | "
            f"Duration: {video['duration']}s | "
            f"Score: {score}"
        )

    best = select_best_video(videos, query, 5)

    print("\n===== SELECTED VIDEO =====")

    if best:
        print("Selected ID:", best["video_id"])
        print("Selected URL:", best["url"])
    else:
        print("No suitable footage found.")
