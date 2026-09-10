import threading
from profile import apply_profile_update, build_system_prompt, wants_profile_update
from llm import chat
from tts import speak
from reminder.alertMe import check_reminders
import time

history = []

def reminder_loop():
    while True:
        try:
            check_reminders()
        except Exception as e:
            print(f"[ERROR] Reminder check failed: {e}")
        time.sleep(30)

reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
reminder_thread.start()
print("[INFO] Reminder checker started in background.")

try:
    while True:
        try:
            user_input = input("You: ")
            
            print("ini hasil input user: ", user_input)

            print("thinking, please wait......")

            # feature update my profile
            if wants_profile_update(user_input):
                apply_profile_update(user_input)
                text = "Oke, profil kamu sudah saya perbarui."
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": text})
                history = history[-4:]
                print("E.V : ", text)
                speak(text)
                continue

            resultHistory = history.append({"role": "user", "content": user_input})
            # print("result history: ", resultHistory)
            
            history = history[-4:]

            messages = [
                {
                    "role": "system",
                    "content": build_system_prompt(),
                },
                *history,
            ]

            response = chat(messages)
            text = response["message"]["content"]
            # print("dapet responsenya nih ", text)
            print("E.V : ", text)
            speak(text)

            history.append({"role": "assistant", "content": text})
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[Error] {e}")
            print("Something went wrong. Please try again.")
except KeyboardInterrupt:
    print("\nGoodbye! E.V shutting down...")
