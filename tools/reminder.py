import json
import re
from pathlib import Path

REMINDERS_FILE = Path(__file__).parent.parent / "reminder" / "reminders.json"


def _load_reminders() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    with open(REMINDERS_FILE, "r") as f:
        return json.load(f)


def _save_reminders(reminders: list[dict]):
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def _normalize_time(time_str: str) -> str:
    time_str = time_str.strip().lower()

    match_24h = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if match_24h:
        h, m = int(match_24h.group(1)), int(match_24h.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    match_24h_sec = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", time_str)
    if match_24h_sec:
        h, m = int(match_24h_sec.group(1)), int(match_24h_sec.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    match_12h = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", time_str)
    if match_12h:
        h, m, period = int(match_12h.group(1)), int(match_12h.group(2)), match_12h.group(3)
        if period == "am":
            if h == 12:
                h = 0
        else:
            if h != 12:
                h += 12
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    return time_str


async def set_reminder_handler(time: str, message: str) -> str:
    normalized_time = _normalize_time(time)
    reminders = _load_reminders()
    reminders.append({"time": normalized_time, "message": message})
    _save_reminders(reminders)
    return f"Reminder set for {normalized_time}: {message}"


async def get_reminders_handler() -> str:
    reminders = _load_reminders()
    if not reminders:
        return "No active reminders."
    lines = [f"- {r['time']}: {r['message']}" for r in reminders]
    return "Active reminders:\n" + "\n".join(lines)


async def delete_reminder_handler(time: str) -> str:
    reminders = _load_reminders()
    original_count = len(reminders)
    reminders = [r for r in reminders if r["time"] != time]
    if len(reminders) == original_count:
        return f"No reminder found at {time}."
    _save_reminders(reminders)
    return f"Reminder at {time} deleted."
