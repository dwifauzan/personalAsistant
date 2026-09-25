"""
Modul Text-to-Speech (TTS) menggunakan Kokoro.

Fungsi utama:
- speak(): Mengubah text menjadi suara dan memutarnya melalui speaker
- Menggunakan model Kokoro ONNX untuk generate audio
- Mendukung berbagai pilihan suara (pria/wanita, berbagai bahasa)

Konfigurasi suara ada di config.py:
- KOKORO_VOICE: pilihan suara (am_fenrir = deep male, af_heart = female)
- KOKORO_SPEED: kecepatan bicara (1.0 = normal)
- KOKORO_LANGUAGE: bahasa (en-us, id-id, dll)
"""

import threading
from pathlib import Path

import numpy as np
import sounddevice as nacsound
from kokoro_onnx import Kokoro
from .config import (
    KOKORO_LANGUAGE,
    KOKORO_MODEL_PATH,
    KOKORO_SAMPLE_RATE,
    KOKORO_SPEED,
    KOKORO_VOICE,
    KOKORO_VOICES_PATH,
    TTS_ENABLED,
)

_engine = None
_engine_lock = threading.Lock()
_speech_lock = threading.Lock()
_FADE_MS = 12
_EDGE_SILENCE_MS = 20

class _FloatSpeedSession:
    """
    Wrapper untuk ONNX session yang mengkonversi speed ke float32.
    
    Kokoro ONNX model membutuhkan parameter speed dalam format float32,
    tapi kadang dikirim dalam format lain. Class ini memastikan konversi
    yang benar sebelum menjalankan inference.
    """
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def run(self, output_names, input_feed, *args, **kwargs):
        input_feed = dict(input_feed)
        if "speed" in input_feed:
            input_feed["speed"] = np.asarray(input_feed["speed"], dtype=np.float32)
        return self._session.run(output_names, input_feed, *args, **kwargs)

def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                model_paths = (Path(KOKORO_MODEL_PATH), Path(KOKORO_VOICES_PATH))
                missing = [str(path) for path in model_paths if not path.is_file()]
                if missing:
                    raise FileNotFoundError(
                        "Missing Kokoro model files: " + ", ".join(missing)
                    )

                _engine = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
                _engine.sess = _FloatSpeedSession(_engine.sess)
    return _engine

def should_speak(text) -> bool:
    """
    Return True if text has speakable content.

    Kokoro crashes with "need at least one array to concatenate" on
    empty/whitespace input, so callers must check this first.
    """
    return bool(text and text.strip())


def _prepare_audio(audio, sample_rate: int) -> np.ndarray:
    """Make generated audio safe for a speaker and suppress edge clicks."""
    prepared = np.asarray(audio, dtype=np.float32).reshape(-1)
    prepared = np.nan_to_num(prepared, nan=0.0, posinf=0.0, neginf=0.0)
    prepared = np.clip(prepared, -1.0, 1.0)

    fade_samples = min(
        len(prepared) // 2,
        max(1, int(sample_rate * _FADE_MS / 1000)),
    )
    if fade_samples:
        prepared[:fade_samples] *= np.linspace(
            0.0, 1.0, fade_samples, dtype=np.float32
        )
        prepared[-fade_samples:] *= np.linspace(
            1.0, 0.0, fade_samples, dtype=np.float32
        )
    silence_samples = int(sample_rate * _EDGE_SILENCE_MS / 1000)
    if silence_samples:
        prepared = np.pad(
            prepared,
            (silence_samples, silence_samples),
            mode="constant",
        )
    return prepared


def speak(text):
    """
    Mengubah text menjadi suara dan memutarnya melalui speaker.
    
    Args:
        text: String yang akan diubah menjadi suara
    
    Contoh:
        speak("Halo, apa kabar?")
    
    Note:
        - Engine diinisialisasi otomatis pada pemanggilan pertama
        - Menggunakan konfigurasi dari config.py (voice, speed, language)
        - Audio langsung diputar setelah di-generate (blocking)
        - Empty/whitespace text is skipped silently (Kokoro crashes on it)
    """
    if not TTS_ENABLED:
        return None
    if not should_speak(text):
        print("[Warning] speak() called with empty text, skipping TTS.")
        return None

    # The reminder thread and the dashboard worker can both call speak().
    # Serialize generation and playback so sounddevice never has two streams
    # competing for the same speaker.
    with _speech_lock:
        engine = _get_engine()
        audio, sample_rate = engine.create(
            text,
            voice=KOKORO_VOICE,
            speed=KOKORO_SPEED,
            lang=KOKORO_LANGUAGE,
        )
        actual_sample_rate = sample_rate or KOKORO_SAMPLE_RATE
        audio = _prepare_audio(audio, actual_sample_rate)
        nacsound.play(audio, samplerate=actual_sample_rate)
        nacsound.wait()
