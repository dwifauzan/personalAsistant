"""
Modul untuk mengelola profil user.

Fungsi utama:
- load_profile(): Membaca profil dari file profile.md
- build_system_prompt(): Membuat system prompt dengan profil user
- wants_profile_update(): Mendeteksi apakah user ingin update profil
- apply_profile_update(): Mengupdate profil berdasarkan permintaan user

Profil disimpan di profile.md dan digunakan AI untuk memberikan
response yang lebih personal sesuai informasi user.
"""

import re
import shutil

import ollama

from config import MODEL_NAME

PROFILE_PATH = "profile.md"
PROFILE_BACKUP_PATH = "profile.md.bak"

# Pattern untuk mendeteksi permintaan update profil (Indonesia & English)
UPDATE_PATTERNS = [
    r"\bupdate\s+(?:profil|profile|data|info|informasi)(?:ku|mu|nya)?\b",
    r"\bubah\s+(?:profil|profile|data|info|informasi)(?:ku|mu|nya)?\b",
    r"\btambah(?:kan)?\s+(?:profil|profile|data|info|informasi)(?:ku|mu|nya)?\b",
    r"\b(?:profil|profile|data|info|informasi)(?:ku|mu|nya)?\s+(?:update|ubah|tambah)\b",
    r"\bsimpan\s+(?:ini|itu|informasi|data)\b",
    r"\b(ingatkan|ingetin)\s+(?:bahwa|kalau|kalo)\b",
    r"\bset\s+(?:my|the)\s+(?:profile|info|information)\b",
    r"\bupdate\s+my\s+(?:profile|info|information)\b",
    r"\badd\s+(?:to\s+)?my\s+(?:profile|info|information)\b",
    r"\bchange\s+(?:my|the)\s+(?:profile|info|information)\b",
]


def load_profile():
    """
    Membaca konten profil dari file profile.md.
    
    Returns:
        String berisi konten profil user
    
    Example:
        profile = load_profile()
        print(profile)  # "Nama: Budi\nUmur: 25\n..."
    """
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def build_system_prompt():
    """
    Membuat system prompt untuk AI dengan menyertakan profil user.
    
    Returns:
        String berisi system prompt lengkap dengan instruksi dan profil user
    
    Note:
        System prompt ini yang menentukan perilaku AI dan memberikan
        konteks tentang user agar response lebih personal.
    """
    profile = load_profile()
    # adjust instruction to ai
    return (
        "You are E.V, a concise voice assistant. friendly and cheerful assistant, be warm and use humor. Reply in 1-2 short sentences, "
              "Your are a professional assistant, Be helpful and informative.\n"
              f"User profile:\n{profile}\n"
              "Use the profile information when relevant to the user's question."
    )


def wants_profile_update(text):
    """
    Mendeteksi apakah user ingin mengupdate profil berdasarkan text input.
    
    Args:
        text: String input dari user
    
    Returns:
        True jika text mengandung pattern permintaan update profil, False jika tidak
    
    Example:
        wants_profile_update("update profilku")  # True
        wants_profile_update("apa kabar")        # False
    """
    return bool(re.search("|".join(UPDATE_PATTERNS), text, re.I))


def apply_profile_update(user_request):
    """
    Mengupdate profil user berdasarkan permintaan menggunakan AI.
    
    Args:
        user_request: String permintaan update dari user
                      (contoh: "nama saya budi", "umur saya 25 tahun")
    
    Returns:
        String berisi profil yang sudah diupdate
    
    Flow:
        1. Load profil saat ini
        2. Kirim ke AI dengan instruksi update
        3. AI akan modify existing info atau append info baru
        4. Simpan profil baru ke file
        5. Return profil yang sudah diupdate
    
    Note:
        - AI hanya mengubah informasi yang diminta, tidak mengubah bagian lain
        - Jika info sudah ada, akan di-update. Jika belum ada, akan ditambah
        - Format markdown dihapus jika AI secara tidak sengaja menambahkannya
    """
    current_profile = load_profile()
    prompt = (
        "You are a profile updater assistant. Your job is to update the user profile below "
        "based ONLY on the user's request.\n\n"
        "RULES:\n"
        "1. If the request mentions information already present in the profile "
        "   (e.g., name, age, location, language, education, work, health history), "
        "   MODIFY ONLY the existing line that matches. Do not rewrite unrelated lines.\n"
        "2. If the request mentions completely NEW information not in the profile, "
        "   APPEND it as a new line at the bottom.\n"
        "3. Preserve the existing format, headings, and all unrelated information exactly.\n"
        "4. Do NOT add explanations, greetings, or markdown code blocks.\n"
        "5. Return ONLY the updated profile content.\n\n"
        f"CURRENT PROFILE:\n{current_profile}\n\n"
        f"USER REQUEST:\n{user_request}\n\n"
        "UPDATED PROFILE:"
    )
    response = ollama.generate(model=MODEL_NAME, prompt=prompt)
    new_profile = response["response"].strip()

    # Hapus pembungkus markdown jika LLM secara tidak sengaja mengembalikan ```
    if new_profile.startswith("```"):
        new_profile = new_profile.strip("`").strip()
        if new_profile.lower().startswith("markdown"):
            new_profile = new_profile.split("\n", 1)[-1].strip()

    new_profile = re.sub(r"#+\s+", "", new_profile)
    new_profile = re.sub(r"\*\*([^*]+)\*\*", r"\1", new_profile)
    new_profile = re.sub(r"\*([^*]+)\*", r"\1", new_profile)
    new_profile = re.sub(r"`([^`]+)`", r"\1", new_profile)

    if not new_profile or len(new_profile) < len(current_profile) // 2:
        print(f"[Warning] Profile update rejected: output too short or empty")
        return current_profile

    shutil.copy2(PROFILE_PATH, PROFILE_BACKUP_PATH)

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        f.write(new_profile)
    return new_profile
