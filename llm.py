"""
Modul untuk komunikasi dengan AI model (Ollama).

Fungsi utama:
- chat(): Mengirim pesan ke AI dan mendapatkan response
- Otomatis melakukan web search jika AI tidak yakin atau butuh info real-time
- Menggunakan searching.py untuk mengambil konten web/berita
"""

import ollama

from config import MODEL_NAME, NUM_PREDICT
from tools.searching import search_for_context

def chat(messages):
    print("Sending messages to AI model...")
    """
    Mengirim pesan ke AI dan mendapatkan response.
    
    Args:
        messages: List of dict dengan format:
                  [{"role": "user/assistant/system", "content": "pesan"}]
    
    Returns:
        Dict dengan format: {"message": {"content": "response AI"}}
    
    Flow:
        1. Kirim pesan ke AI (Ollama)
        2. Cek apakah AI butuh informasi tambahan (ragu-ragu, butuh info real-time)
        3. Jika ya, lakukan web search dan kirim ulang dengan konteks tambahan
        4. Return response final dari AI
    """
    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={"num_predict": NUM_PREDICT},
    )

    content = response["message"]["content"]
    
    print("get it, data: ", content)
    # Ambil pesan terakhir dari user untuk analisis
    user_content = next(
        (
            message["content"]
            for message in reversed(messages)
            if message["role"] == "user"
        ),
        "",
    )

    # Cek apakah perlu mencari informasi tambahan dari web
    search_text = search_for_context(
        user_content,
        content,
    )

    # Jika tidak perlu search, return response langsung
    if not search_text:
        return response

    # Jika perlu search, tambahkan hasil pencarian ke system prompt
    new_messages = [
        (
            {
                "role": "system",
                "content": message["content"]
                + "\n\nYou were given full web page contents below. "
                  "Read them carefully, summarize the key information, "
                  "and answer the user based ONLY on what is contained "
                  "in those pages. If the pages do not contain a specific "
                  "fact, number, price, date, or event, say clearly that "
                  "the sources do not provide it. NEVER fill in numbers, "
                  "prices, names, or dates from your own memory or training "
                  "data. Cite the source number when possible."
                + "\n\nWEB PAGE CONTENTS:\n"
                + search_text,
            }
            if message["role"] == "system"
            else message
        )
        for message in messages
    ]

    # Kirim ulang dengan konteks tambahan dari web search
    return ollama.chat(
        model=MODEL_NAME,
        messages=new_messages,
        options={
            "num_predict": NUM_PREDICT,
            "num_ctx": 8192,
        },
    )
