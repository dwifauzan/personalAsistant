from profile import apply_profile_update, build_system_prompt, wants_profile_update
from llm import chat
from tts import speak

history = []

while True:
    user_input = input("You: ")

    print("thinking, please wait......")

    if wants_profile_update(user_input):
        apply_profile_update(user_input)
        text = "Oke, profil kamu sudah saya perbarui."
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": text})
        history = history[-8:]
        print("E.V : ", text)
        speak(text)
        continue

    history.append({"role": "user", "content": user_input})
    history = history[-8:]

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        *history,
    ]

    response = chat(messages)
    text = response["message"]["content"]
    print("E.V : ", text)
    speak(text)

    history.append({"role": "assistant", "content": text})
