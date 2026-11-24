from app.services.audio.audio_mixer import mix_audio


def main():
    result = mix_audio(
        narration_path="storage/audio/project_9999/narration.mp3",
        music_path="storage/music/fight34.mp3",
        output_path="storage/audio/project_9999/final_audio.mp3",
        music_volume=0.35,
        voice_volume=1.0
    )

    print("\nAudio mixing successful!")
    print(f"Output: {result['output_path']}")
    print(f"File size: {result['file_size'] / 1024:.2f} KB")
    print(f"Ducking enabled: {result['ducking_enabled']}")


if __name__ == "__main__":
    main()