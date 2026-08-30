"""
Main entry point untuk voice assistant.

Program ini menjalankan loop interaktif dimana user bisa berbicara dengan AI.
AI akan mendengarkan input text, memprosesnya, dan memberikan response baik
dalam bentuk text maupun suara (TTS).

Fitur utama:
- Chat interaktif dengan AI (Ollama)
- Voice output menggunakan Kokoro TTS   
- Update profil user secara dinamis
- Pencarian web otomatis untuk informasi real-time
"""

from profile import apply_profile_update, build_system_prompt, wants_profile_update
from llm import chat
from tts import speak

# Menyimpan riwayat percakapan (max 8 pesan terakhir untuk konteks)
history = []

while True:
    # Membaca input dari user
    user_input = input("You: ")

    print("thinking please wait......")

    # Cek apakah user ingin mengupdate profil
    if wants_profile_update(user_input):
        apply_profile_update(user_input)
        text = "Oke, profil kamu sudah saya perbarui."
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": text})
        history = history[-8:]
        print("E.V : ", text)
        speak(text)
        continue

    # Menambahkan pesan user ke riwayat
    history.append({"role": "user", "content": user_input})
    history = history[-8:]

    # Menyusun messages untuk AI dengan system prompt yang berisi profil user
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        *history,
    ]

    # Mendapatkan response dari AI
    text = chat(messages)["message"]["content"]
    print("E.V : ", text)
    speak(text)

    # Menambahkan response AI ke riwayat
    history.append({"role": "assistant", "content": text})
