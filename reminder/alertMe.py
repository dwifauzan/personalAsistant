import sys
import json
from pathlib import Path
from datetime import datetime
import time

sys.path.append(str(Path(__file__).parent.parent))
from tts import speak

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


def check_reminders():
    current_time = checkTime()
    reminders = load_reminders()

    print(f"[DEBUG] Current time: {current_time}, Active reminders: {len(reminders)}")

    for reminder in reminders:
        print(f"[DEBUG] Checking reminder: {reminder['time']} against current: {current_time}")
        if reminder["time"] == current_time:
            print(f"[DEBUG] MATCH FOUND! Triggering reminder...")
            try:
                speak(reminder["message"])
                print(f"Reminder triggered: {reminder['message']}")
            except Exception as e:
                print(f"[ERROR] Failed to speak reminder: {e}")
            remove_reminder(current_time)
            break


while True:
    try:
        check_reminders()
    except Exception as e:
        print(f"[ERROR] Error in check_reminders: {e}")
    time.sleep(30)
