
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.subtitle_renderer import render_subtitles


def main():
    video_path = "storage/rendered/project_4/timeline_video.mp4"
    audio_path = "storage/audio/project_9999/narration.mp3"

    output_path = "storage/rendered/project_4/subtitled_video.mp4"

    print("Generating word timestamps...")

    timestamps = generate_word_timestamps(audio_path)

    print(f"Words detected: {len(timestamps['words'])}")

    print("\nRendering animated subtitles...")

    result = render_subtitles(
        video_path="storage/rendered/project_4/timeline_video.mp4",
        audio_path="storage/audio/project_9999/final_audio.mp3",
        words=timestamps["words"],
        output_path="storage/rendered/project_4/subtitled_video.mp4"
    )

    print("\nSubtitle rendering successful!")
    print(f"Output: {result['output_path']}")
    print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")
    print(f"Words: {result['word_count']}")
    print(f"Caption groups: {result['caption_groups']}")


if __name__ == "__main__":
    main()
