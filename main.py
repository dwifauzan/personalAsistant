import threading
import queue

from app.llm import chat
from app.profile import apply_profile_update, build_system_prompt, wants_profile_update
from reminder.alertMe import check_reminders
from app.tts import should_speak, speak
from app.ui.tui import run_dashboard


history: list[dict] = []
shutdown_event = threading.Event()


def reminder_loop(speech_queue: queue.Queue[str]) -> None:
    while not shutdown_event.is_set():
        try:
            check_reminders(speak_fn=speech_queue.put)
        except Exception as error:
            print(f"[ERROR] Reminder check failed: {error}")
        shutdown_event.wait(30)


def ask_assistant(user_input: str) -> str:
    history.append({"role": "user", "content": user_input})
    del history[:-4]

    if wants_profile_update(user_input):
        apply_profile_update(user_input)
        text = "Okay, your profile has been updated."
    else:
        messages = [
            {"role": "system", "content": build_system_prompt()},
            *history,
        ]
        response = chat(messages)
        text = (response["message"]["content"] or "").strip()
        if not should_speak(text):
            text = "I found the information but couldn't form a reply. Please ask again in a simpler way."

    history.append({"role": "assistant", "content": text})
    del history[:-4]
    return text


def main() -> None:
    speech_queue: queue.Queue[str] = queue.Queue()
    reminder_thread = threading.Thread(
        target=reminder_loop, args=(speech_queue,), daemon=True
    )
    reminder_thread.start()
    try:
        run_dashboard(ask_assistant, speak, history, shutdown_event, speech_queue)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_event.set()
        print("\nGoodbye! E.V shutting down...")


if __name__ == "__main__":
    main()
