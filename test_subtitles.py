
from app.services.audio.subtitles import generate_word_timestamps

audio_path = "storage/audio/project_9999/narration.mp3"

print("Generating word timestamps...")

result = generate_word_timestamps(audio_path)

print("\nLanguage:", result["language"])
print("Duration:", result["duration"])
print("Total words:", len(result["words"]))

print("\nFirst 20 words:")
for word in result["words"][:20]:
    print(word)
