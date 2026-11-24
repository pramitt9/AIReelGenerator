
from app.services.audio.subtitles import generate_word_timestamps


def main():
    audio_path = "storage/audio/project_9999/narration.mp3"

    print("Generating word-level timestamps...")

    try:
        result = generate_word_timestamps(audio_path)

        print("\nSubtitle generation successful!")
        print(f"Language: {result['language']}")
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Total words: {len(result['words'])}")

        print("\nFirst 20 words:")
        for word in result["words"][:20]:
            print(
                f"{word['start']:>7.2f}s - "
                f"{word['end']:>7.2f}s  "
                f"{word['word']}"
            )

    except Exception as error:
        print("\nSubtitle generation failed!")
        print(f"Error: {error}")
        raise


if __name__ == "__main__":
    main()
