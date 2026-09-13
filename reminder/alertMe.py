import sys
import json
from pathlib import Path
from datetime import datetime
import time

sys.path.append(str(Path(__file__).parent.parent))
from app.tts import speak

REMINDERS_FILE = Path(__file__).parent / "reminders.json"


def checkTime():
    timeRightNow = datetime.now()
    getTime = timeRightNow.strftime("%H:%M")
    return getTime


def load_reminders():
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def remove_reminder(time_str):
    reminders = load_reminders()
    reminders = [r for r in reminders if r["time"] != time_str]
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def check_reminders(speak_fn=speak):
    current_time = checkTime()
    reminders = load_reminders()

    for reminder in reminders:
        if reminder["time"] == current_time:
            try:
                speak_fn(reminder["message"])
            except Exception as e:
                print(f"[ERROR] Failed to speak reminder: {e}")
            remove_reminder(reminder["time"])
            break


def main():
    while True:
        try:
            check_reminders()
        except Exception as e:
            print(f"[ERROR] Error in check_reminders: {e}")
        time.sleep(30)


if __name__ == "__main__":
    main()
