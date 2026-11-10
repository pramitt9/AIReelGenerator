
import subprocess
import numpy as np
from faster_whisper import WhisperModel


_model = None


def get_model():
    """Load Whisper once and reuse it."""
    global _model

    if _model is None:
        _model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

    return _model


def load_audio(audio_path: str) -> np.ndarray:
    """Decode audio using FFmpeg instead of PyAV."""

    command = [
        "ffmpeg",
        "-i", audio_path,
        "-f", "s16le",
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        "-"
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )

    audio = np.frombuffer(result.stdout, dtype=np.int16)

    return audio.astype(np.float32) / 32768.0


def generate_word_timestamps(audio_path: str) -> dict:
    audio = load_audio(audio_path)
    model = get_model()

    segments, info = model.transcribe(
        audio,
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
        raise ValueError("No speech detected in the audio.")

    return {
        "language": info.language,
        "duration": info.duration,
        "words": words
    }
