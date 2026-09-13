"""Copilot-inspired curses dashboard for E.V."""

from __future__ import annotations

import curses
import contextlib
import io
import queue
import threading
import time
from datetime import datetime
from textwrap import wrap

from ..config import MODEL_NAME
from ..metrics import UsageSnapshot, record_input, snapshot
from tools.reminder import _load_reminders


class AssistantDashboard:
    """Responsive terminal interface for chat, reminders, and AI status."""

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
        self.speech_queue = speech_queue
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.input_buffer = ""
        self.status = "Ready"
        self.audio_status = "Idle"
        self.processing = False
        self.activity = "Ready"
        self._worker: threading.Thread | None = None
        self.messages: list[tuple[str, str]] = [
            ("system", "Welcome back. Ask E.V anything.")
        ]

    def run(self) -> None:
        curses.curs_set(1)
        self.screen.nodelay(True)
        self.screen.keypad(True)
        self._setup_colors()

        while not self.shutdown_event.is_set():
            self._process_events()
            self._play_pending_speech()
            self._draw()
            self._handle_key(self.screen.getch())
            time.sleep(0.05)

    def _handle_key(self, key: int) -> None:
        if key == -1:
            return
        if key in (3, 17):
            self.shutdown_event.set()
        elif key in (10, 13, curses.KEY_ENTER):
            self._submit()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.input_buffer = self.input_buffer[:-1]
        elif key == 12:  # Ctrl-L
            self.messages = []
        elif 32 <= key <= 126 and not self.processing:
            self.input_buffer += chr(key)

    def _setup_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)   # brand / borders
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # healthy / E.V
        curses.init_pair(3, curses.COLOR_YELLOW, -1) # active / input
        curses.init_pair(4, curses.COLOR_RED, -1)    # errors
        curses.init_pair(5, curses.COLOR_BLUE, -1)   # user
        curses.init_pair(6, curses.COLOR_MAGENTA, -1) # accent
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)  # input

    def _submit(self) -> None:
        text = self.input_buffer.strip()
        if not text or self.processing:
            return
        self.input_buffer = ""
        record_input(len(text))
        self.messages.append(("you", text))
        self.processing = True
        self.status = "Thinking"
        self._worker = threading.Thread(
            target=self._answer, args=(text,), daemon=True
        )
        self._worker.start()

    def _answer(self, text: str) -> None:
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                response = self.ask(text)
            for line in output.getvalue().splitlines():
                if line.strip():
                    self.events.put(("activity", line.strip()))
            self.events.put(("response", response))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _process_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                return
            self.processing = False
            if event == "activity":
                self.activity = payload
            elif event == "response":
                self.messages.append(("ev", payload))
                self.speech_queue.put(payload)
                self.status = "Ready"
            else:
                self.messages.append(("error", payload))
                self.status = "Error"

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

    def _draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 18 or width < 76:
            self._write(1, 2, "Terminal too small", 4, curses.A_BOLD)
            self._write(3, 2, "Resize to at least 76 columns x 18 rows.", 0)
            self.screen.refresh()
            return

        now = datetime.now()
        usage = snapshot()
        self._draw_header(width, now, usage)

        sidebar_width = min(34, max(28, width // 3))
        chat_width = width - sidebar_width - 3
        content_top = 4
        content_height = height - 8
        self._draw_chat(content_top, 1, content_height, chat_width)
        self._draw_sidebar(
            content_top,
            chat_width + 2,
            content_height,
            sidebar_width,
            usage,
            now,
        )
        self._draw_input(height, width)
        self.screen.refresh()

    def _draw_header(self, width: int, now: datetime, usage: UsageSnapshot) -> None:
        self._fill(0, 0, width, " ", 1)
        self._write(0, 2, "✦ E.V", 1, curses.A_BOLD)
        self._write(0, 10, "PERSONAL AI", 0, curses.A_BOLD)
        self._write(0, max(2, width - 37), f"MODEL  {MODEL_NAME}"[:20], 0)
        self._write(0, width - 16, now.strftime("%H:%M:%S"), 2, curses.A_BOLD)
        backend = usage.backend if usage.backend != "not connected" else "offline"
        self._write(
            1,
            2,
            f"● {self.status.upper():<10}  AUDIO {self.audio_status.upper():<9}  "
            f"BACKEND {backend.upper()}",
            3 if self.processing or self.audio_status == "Speaking" else 2,
        )
        self._write(2, 0, "─" * width, 1)

    def _draw_chat(self, top: int, left: int, height: int, width: int) -> None:
        self._write(top, left, "CHAT", 1, curses.A_BOLD)
        self._write(top, left + 5, "─" * max(0, width - 5), 1)
        inner_width = width - 2
        rendered: list[tuple[str, str, int]] = []
        for role, message in self.messages:
            color = {"you": 5, "ev": 2, "error": 4, "system": 6}.get(role, 0)
            label = {"you": "YOU", "ev": "E.V", "error": "ERROR", "system": "SYSTEM"}.get(
                role, role.upper()
            )
            rendered.append((label, "", color))
            rendered.extend(("", line, color) for line in _wrap(message, inner_width))

        available = height - 2
        row = top + 1
        for label, text, color in rendered[-available:]:
            if row >= top + height:
                break
            if label:
                self._write(row, left, label, color, curses.A_BOLD)
            else:
                self._write(row, left + 2, text[:width - 4], color)
            row += 1

    def _draw_sidebar(
        self,
        top: int,
        left: int,
        height: int,
        width: int,
        usage: UsageSnapshot,
        now: datetime,
    ) -> None:
        self._panel(top, left, height, width, "WORKSPACE")
        reminders = _load_reminders()
        elapsed = max(0, int((now - usage.started_at).total_seconds()))
        rows = [
            ("TIME", now.strftime("%a, %d %b")),
            ("CLOCK", now.strftime("%H:%M:%S")),
            ("", ""),
            ("REMINDERS", str(len(reminders))),
        ]
        for reminder in reminders[:3]:
            rows.append(("", f"{reminder.get('time', '--:--')}  {reminder.get('message', '')}"))
        rows.extend(
            [
                ("", ""),
                ("AI USAGE", ""),
                ("MODEL CALLS", str(usage.model_calls)),
                ("TOOL CALLS", str(usage.tool_calls)),
                ("INPUT", f"{usage.input_chars:,} chars"),
                ("OUTPUT", f"{usage.output_chars:,} chars"),
                ("SESSION", f"{elapsed // 60}m {elapsed % 60:02d}s"),
            ]
        )
        row = top + 1
        for label, value in rows:
            if row >= top + height - 1:
                break
            color = 6 if label in {"REMINDERS", "AI USAGE"} else 0
            text = f"{label:<12} {value}" if label else f"  {value}"
            self._write(row, left + 2, text[:width - 3], color, curses.A_BOLD if label in {"REMINDERS", "AI USAGE"} else 0)
            row += 1

    def _draw_input(self, height: int, width: int) -> None:
        self._fill(height - 4, 0, width, " ", 1)
        self._write(height - 4, 2, f"STATUS  {self.activity}"[: width - 4], 3)
        self._fill(height - 3, 0, width, " ", 7)
        self._write(
            height - 3,
            2,
            "› " + self.input_buffer[: width - 6],
            7,
            curses.A_BOLD,
        )
        self._write(height - 2, 2, "Enter send   Ctrl-L clear   Ctrl-Q exit", 0)
        self._write(height - 2, width - 20, "E.V is ready"[:18], 2)
        self.screen.move(height - 3, min(width - 1, 4 + len(self.input_buffer)))

    def _panel(self, top: int, left: int, height: int, width: int, title: str) -> None:
        if width < 6 or height < 3:
            return
        self._write(top, left, f"╭─ {title} " + "─" * max(0, width - len(title) - 5), 1)
        for row in range(top + 1, top + height - 1):
            self._write(row, left, "│" + " " * max(0, width - 2) + "│", 1)
        self._write(top + height - 1, left, "╰" + "─" * max(0, width - 2) + "╯", 1)

    def _fill(self, row: int, col: int, width: int, char: str, color: int = 0) -> None:
        self._write(row, col, char * max(0, width), color)

    def _write(self, row: int, col: int, text: str, color: int = 0, attr: int = 0) -> None:
        try:
            max_width = max(0, self.screen.getmaxyx()[1] - col - 1)
            self.screen.addnstr(row, col, text, max_width, color_pair(color) | attr)
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
