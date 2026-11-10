
from faster_whisper import WhisperModel


def generate_word_timestamps(audio_path: str) -> dict:
    """
    Transcribe an audio file and return word-level timestamps.
    Uses CPU with int8 quantization to keep resource usage manageable.
    """

    model = WhisperModel(
        "small",
        device="cpu",
        compute_type="int8"
    )

    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True
    )

    words = []

    for segment in segments:
        if segment.words:
            for word in segment.words:
                words.append({
                    "word": word.word.strip(),
                    "start": round(word.start, 3),
                    "end": round(word.end, 3)
                })

    if not words:
        raise ValueError("No speech detected in the audio file.")

    return {
        "language": info.language,
        "duration": info.duration,
        "words": words
    }
