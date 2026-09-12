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
from config import (
    KOKORO_LANGUAGE,
    KOKORO_MODEL_PATH,
    KOKORO_SAMPLE_RATE,
    KOKORO_SPEED,
    KOKORO_VOICE,
    KOKORO_VOICES_PATH,
)

_engine = None
_engine_lock = threading.Lock()
_speech_lock = threading.Lock()

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
    """
    with _speech_lock:
        engine = _get_engine()

        audio, sample_rate = engine.create(
            text,
            voice=KOKORO_VOICE,
            speed=KOKORO_SPEED,
            lang=KOKORO_LANGUAGE,
        )
        nacsound.play(audio, samplerate=sample_rate or KOKORO_SAMPLE_RATE)
        nacsound.wait()
