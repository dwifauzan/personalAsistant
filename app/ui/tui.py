"""Curses dashboard for E.V."""

from __future__ import annotations

import curses
import queue
import threading
import time
from datetime import datetime
from textwrap import wrap

from ..config import MODEL_NAME
from ..metrics import UsageSnapshot, record_input, snapshot
from tools.reminder import _load_reminders


class AssistantDashboard:
    def __init__(
        self,
        screen,
        ask,
        speak,
        history: list[dict],
        shutdown_event: threading.Event,
        speech_queue: queue.Queue[str],
    ):
        self.screen = screen
        self.ask = ask
        self.speak = speak
        self.history = history
        self.shutdown_event = shutdown_event
        self.input_buffer = ""
        self.status = "Ready"
        self.processing = False
        self.audio_status = "Idle"
        self.speech_queue = speech_queue
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.messages: list[tuple[str, str]] = [
            ("system", "E.V dashboard ready. Type a message and press Enter.")
        ]
        self._worker: threading.Thread | None = None

    def run(self) -> None:
        curses.curs_set(1)
        self.screen.nodelay(True)
        self.screen.keypad(True)
        self._setup_colors()

        while not self.shutdown_event.is_set():
            self._process_events()
            self._play_pending_speech()
            self._draw()
            key = self.screen.getch()
            if key == -1:
                time.sleep(0.1)
                continue
            if key in (3, 17):
                self.shutdown_event.set()
                break
            if key in (10, 13, curses.KEY_ENTER):
                self._submit()
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self.input_buffer = self.input_buffer[:-1]
            elif 32 <= key <= 126 and not self.processing:
                self.input_buffer += chr(key)

    def _process_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                return
            if event == "response":
                self.messages.append(("ev", payload))
                self.speech_queue.put(payload)
                self.status = "Ready"
            elif event == "error":
                self.messages.append(("error", payload))
                self.status = "Error"
            self.processing = False

    def _play_pending_speech(self) -> None:
        try:
            text = self.speech_queue.get_nowait()
        except queue.Empty:
            return
        self.audio_status = "Speaking"
        try:
            self.speak(text)
        except Exception as error:
            self.messages.append(("error", f"Speech error: {error}"))
            self.status = "Speech error"
        finally:
            self.audio_status = "Idle"

    def _setup_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)

    def _submit(self) -> None:
        text = self.input_buffer.strip()
        if not text or self.processing:
            return
        self.input_buffer = ""
        record_input(len(text))
        self.messages.append(("you", text))
        self.processing = True
        self.status = "Thinking..."
        self._worker = threading.Thread(
            target=self._answer, args=(text,), daemon=True
        )
        self._worker.start()

    def _answer(self, text: str) -> None:
        try:
            response = self.ask(text)
            self.events.put(("response", response))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 16 or width < 70:
            self._write(0, 0, "Resize the terminal to at least 70x16.", 4)
            self.screen.refresh()
            return

        now = datetime.now()
        usage = snapshot()
        self._write(0, 0, " E.V  PERSONAL ASSISTANT ", 1, curses.A_BOLD)
        self._write(0, max(0, width - 24), now.strftime("%a %d %b  %H:%M:%S"), 2)
        self._write(
            1,
            1,
            f"● LIVE   {self.status}   AUDIO: {self.audio_status}"[: width - 2],
            3 if self.processing or self.audio_status == "Speaking" else 2,
        )
        self._write(2, 0, "─" * width, 1)

        side_width = min(32, max(26, width // 3))
        main_width = width - side_width - 3
        self._panel(4, 1, height - 7, main_width, "Conversation")
        self._panel(4, main_width + 2, height - 7, side_width, "Status")
        self._draw_messages(5, 2, height - 9, main_width - 2)
        self._draw_status(5, main_width + 3, height - 9, side_width - 2, usage, now)

        prompt = " > " + self.input_buffer
        self._write(height - 2, 1, prompt[: width - 2], 2)
        self._write(
            height - 1,
            1,
            f"{self.status}  |  Enter: send  Ctrl-C/Ctrl-Q: quit"[: width - 2],
            3,
        )
        self.screen.move(height - 2, min(width - 1, len(prompt) + 1))
        self.screen.refresh()

    def _draw_messages(self, top: int, left: int, lines: int, width: int) -> None:
        rendered: list[str] = []
        for role, message in self.messages:
            prefix = {"you": "You: ", "ev": "E.V: ", "error": "Error: "}.get(role, "")
            rendered.extend(_wrap(prefix + message, width))
        for row, line in enumerate(rendered[-lines:]):
            self._write(top + row, left, line, 4 if line.startswith("Error:") else 0)

    def _draw_status(
        self,
        top: int,
        left: int,
        lines: int,
        width: int,
        usage: UsageSnapshot,
        now: datetime,
    ) -> None:
        reminders = _load_reminders()
        elapsed = max(0, int((now - usage.started_at).total_seconds()))
        status_lines = [
            ("CLOCK", now.strftime("%H:%M:%S")),
            ("DATE", now.strftime("%Y-%m-%d")),
            ("", ""),
            ("REMINDERS", str(len(reminders))),
            ("AUDIO", self.audio_status),
        ]
        for reminder in reminders[:3]:
            status_lines.append(("", f"{reminder.get('time', '--:--')} {reminder.get('message', '')}"))
        status_lines.extend(
            [
                ("", ""),
                ("AI USAGE", ""),
                ("MODEL", MODEL_NAME),
                ("BACKEND", usage.backend),
                ("MODEL CALLS", str(usage.model_calls)),
                ("TOOL CALLS", str(usage.tool_calls)),
                ("INPUT CHARS", str(usage.input_chars)),
                ("OUTPUT CHARS", str(usage.output_chars)),
                ("SESSION", f"{elapsed // 60}m {elapsed % 60:02d}s"),
            ]
        )
        row = top
        for label, value in status_lines:
            if row >= top + lines:
                break
            text = f"{label:<12} {value}" if label else f"  {value}"
            self._write(row, left, text[:width], 3 if label in {"CLOCK", "AI USAGE"} else 0)
            row += 1

    def _panel(self, top: int, left: int, height: int, width: int, title: str) -> None:
        if width < 4 or height < 3:
            return
        self._write(top, left, f"┌─ {title} " + "─" * max(0, width - len(title) - 5), 1)
        for row in range(top + 1, top + height - 1):
            self._write(row, left, "│" + " " * (width - 1))
        self._write(top + height - 1, left, "└" + "─" * (width - 1), 1)

    def _write(self, row: int, col: int, text: str, color: int = 0, attr: int = 0) -> None:
        try:
            self.screen.addnstr(row, col, text, max(0, self.screen.getmaxyx()[1] - col - 1), color_pair(color) | attr)
        except curses.error:
            pass


def color_pair(number: int) -> int:
    return curses.color_pair(number) if curses.has_colors() else 0


def _wrap(text: str, width: int) -> list[str]:
    if width <= 1:
        return [text[:1]]
    return wrap(text, width, break_long_words=True, break_on_hyphens=False) or [""]


def run_dashboard(
    ask,
    speak,
    history: list[dict],
    shutdown_event: threading.Event,
    speech_queue: queue.Queue[str] | None = None,
) -> None:
    speech_queue = speech_queue or queue.Queue()
    curses.wrapper(
        lambda screen: AssistantDashboard(
            screen, ask, speak, history, shutdown_event, speech_queue
        ).run()
    )
