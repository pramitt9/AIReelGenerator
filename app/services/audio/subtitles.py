import math
import os
import subprocess

import numpy as np
from faster_whisper import WhisperModel


_model = None
_SAMPLE_RATE = 16000


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


def _probe_audio_duration(audio_path: str) -> float:
    """Read the source audio duration with FFprobe."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
    except FileNotFoundError as error:
        raise RuntimeError(
            "FFprobe was not found. Install FFmpeg and ensure it is available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = (error.stderr or "")[-3000:]
        raise RuntimeError(f"Could not inspect narration audio: {details}") from error
    except (TypeError, ValueError) as error:
        raise RuntimeError("FFprobe returned an invalid audio duration.") from error

    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Audio file has an invalid or empty duration.")

    return duration


def load_audio(audio_path: str) -> np.ndarray:
    """Decode audio to mono, 16 kHz float32 samples using FFmpeg."""
    if not audio_path or not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    command = [
        "ffmpeg",
        "-nostdin",
        "-v", "error",
        "-i", audio_path,
        "-f", "s16le",
        "-ac", "1",
        "-ar", str(_SAMPLE_RATE),
        "-acodec", "pcm_s16le",
        "-",
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and ensure it is available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode("utf-8", errors="replace")[-3000:]
        raise RuntimeError(f"Could not decode narration audio: {details}") from error

    if not result.stdout:
        raise ValueError("Audio decoding produced no samples.")

    audio = np.frombuffer(result.stdout, dtype="<i2")
    if audio.size == 0:
        raise ValueError("Audio decoding produced no samples.")

    samples = audio.astype(np.float32) / 32768.0
    if not np.isfinite(samples).all():
        raise ValueError("Decoded audio contains invalid sample values.")

    return samples


def generate_word_timestamps(audio_path: str) -> dict:
    """Transcribe narration and return validated word-level timestamps."""
    if not audio_path or not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    duration = _probe_audio_duration(audio_path)
    audio = load_audio(audio_path)
    expected_samples = int(round(duration * _SAMPLE_RATE))

    if audio.size == 0:
        raise ValueError("No audio samples were decoded.")

    # A small tolerance accounts for container and resampling rounding.
    decoded_duration = audio.size / _SAMPLE_RATE
    if abs(decoded_duration - duration) > max(0.25, 2 / _SAMPLE_RATE):
        raise ValueError(
            "Decoded audio duration does not match the source audio duration."
        )

    model = get_model()

    try:
        segments, info = model.transcribe(
            audio,
            word_timestamps=True,
            vad_filter=True,
        )

        words = []
        for segment in segments:
            if not segment.words:
                continue

            for word in segment.words:
                text = (word.word or "").strip()
                start = float(word.start)
                end = float(word.end)

                if not text:
                    continue
                if not math.isfinite(start) or not math.isfinite(end):
                    raise ValueError("Whisper returned a non-finite word timestamp.")
                if start < 0 or end <= start:
                    raise ValueError("Whisper returned an invalid word timestamp.")
                if end > duration + 0.25:
                    raise ValueError(
                        "Whisper returned a word timestamp beyond the audio duration."
                    )

                words.append({
                    "word": text,
                    "start": round(start, 3),
                    "end": round(end, 3),
                })

    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError(f"Whisper transcription failed: {error}") from error

    if not words:
        raise ValueError("No speech detected in the audio.")

    words.sort(key=lambda item: (item["start"], item["end"]))

    previous_end = 0.0
    for item in words:
        if item["start"] < previous_end - 0.05:
            raise ValueError("Whisper returned overlapping word timestamps.")
        previous_end = item["end"]

    language = getattr(info, "language", None)
    reported_duration = getattr(info, "duration", duration)
    try:
        reported_duration = float(reported_duration)
    except (TypeError, ValueError):
        reported_duration = duration

    if not math.isfinite(reported_duration) or reported_duration <= 0:
        reported_duration = duration

    return {
        "language": language,
        "duration": duration,
        "words": words,
    }
