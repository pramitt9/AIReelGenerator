
from app.services.video_rendering.video_composer import compose_video


def main():
    result = compose_video(
        video_path="storage/rendered/project_4/test_video.mp4",
        audio_path="storage/audio/project_9999/final_audio.mp3",
        output_path="storage/rendered/project_4/complete_test.mp4"
    )

    print("Composition successful!")
    print(f"Output: {result['output_path']}")
    print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
