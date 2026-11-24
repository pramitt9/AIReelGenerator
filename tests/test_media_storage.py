
import os
import subprocess

from app import create_app
from app.services.video_search.pixabay import search_videos
from app.services.video_search.asset_selector import select_best_video
from app.services.storage.media_storage import download_video


app = create_app()

with app.app_context():

    query = "futuristic technology city"

    print("Searching Pixabay...")
    videos = search_videos(query, per_page=10)

    if not videos:
        print("No videos found.")
        raise SystemExit(1)

    print("Selecting best footage...")
    best = select_best_video(videos, query, target_duration=5)

    print("Selected video:", best["video_id"])

    print("\nDownloading video...")

    try:
        file_path = download_video(
            best["url"],
            project_id=9999,
            scene_number=1
        )

        file_size = os.path.getsize(file_path)

        print("\nDownload successful!")
        print("Saved at:", file_path)
        print("File size:", round(file_size / (1024 * 1024), 2), "MB")

        # Verify video using FFprobe
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Video duration:", result.stdout.strip(), "seconds")
            print("FFprobe verification: PASSED")
        else:
            print("FFprobe verification FAILED:")
            print(result.stderr)

    except Exception as e:
        print("ERROR:", e)
