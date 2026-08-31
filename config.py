"""
Konfigurasi utama untuk voice assistant.

File ini berisi semua pengaturan yang dapat diubah sesuai kebutuhan,
termasuk model AI, suara TTS, dan perilaku aplikasi.
"""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent

MODEL_NAME = "llama3.1:latest"

KOKORO_MODEL_PATH = str(_PROJECT_ROOT / "kokoro-v1.0.onnx")

KOKORO_VOICES_PATH = str(_PROJECT_ROOT / "voices-v1.0.bin")

# Bahasa untuk TTS (en-us = English US, id-id = Indonesian)
KOKORO_LANGUAGE = "en-us"

# Suara yang digunakan untuk TTS
# Pilihan suara deep (pria): am_fenrir, am_adam, am_onyx, bm_george
# Pilihan suara female: af_heart, af_bella, af_nicole
KOKORO_VOICE = "af_bella"

# Kecepatan bicara (1.0 = normal, <1.0 = lebih lambat, >1.0 = lebih cepat)
KOKORO_SPEED = 1.0

# Sample rate audio output (Hz)
KOKORO_SAMPLE_RATE = 24000

# Jumlah token maksimum untuk response AI
NUM_PREDICT = 140

# Apakah browser otomatis terbuka saat melakukan pencarian web
OPEN_BROWSER = True

# Async/Tool settings
MAX_CONCURRENT_FETCHES = 3
FETCH_TIMEOUT = 15
MAX_RETRIES = 2
MAX_TOOL_ROUNDS = 3
