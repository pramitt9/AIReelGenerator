
import subprocess
from pathlib import Path

from app import create_app
from app.services.audio.tts import generate_narration


app = create_app()

storyboard = {
    "title": "The Future of Artificial Intelligence",
    "scenes": [
        {
            "narration": "Artificial intelligence is transforming our cities."
        },
        {
            "narration": "Machines are learning to perform complex tasks."
        },
        {
            "narration": "The future of AI is still being written."
        }
    ]
}

with app.app_context():

    try:
        print("Generating narration...")

        result = generate_narration(
            storyboard,
            project_id=9999
        )

        print("\nNarration generated successfully!")
        print("Saved at:", result["audio_path"])
        print(
            "File size:",
            round(result["file_size"] / (1024 * 1024), 2),
            "MB"
        )

        # Verify audio using FFprobe
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries",
                "format=duration:format=size",
                "-of", "default=noprint_wrappers=1",
                result["audio_path"]
            ],
            capture_output=True,
            text=True
        )

        if probe.returncode == 0:
            print("\nFFprobe verification: PASSED")
            print(probe.stdout)
        else:
            print("\nFFprobe verification FAILED")
            print(probe.stderr)

    except Exception as e:
        print("ERROR:", e)
