
from app import create_app
from app.services.video_search.pixabay import search_videos

app = create_app()

with app.app_context():
    try:
        results = search_videos("futuristic technology city", per_page=5)

        print(f"\nVideos found: {len(results)}")

        for video in results:
            print("\n------------------------")
            print("Video ID:", video["video_id"])
            print("Duration:", video["duration"], "seconds")
            print("Resolution:", video["width"], "x", video["height"])
            print("URL:", video["url"])

    except Exception as e:
        print("ERROR:", e)
