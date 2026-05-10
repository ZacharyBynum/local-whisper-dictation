#!/usr/bin/env python3
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

ICON_READY = "audio-input-microphone"
ICON_ACTIVE = "audio-status-microphone-high-symbolic"
ICON_ERROR = "dialog-error-symbolic"
CONFIG_DIR = pathlib.Path(os.environ.get("LOCAL_WHISPER_CONFIG_DIR", "~/.config/local-whisper")).expanduser()
STATE_DIR = pathlib.Path(os.environ.get("LOCAL_WHISPER_STATE_DIR", "~/.local/state/local-whisper")).expanduser()
VOCABULARY_PATH = pathlib.Path(
    os.environ.get("LOCAL_WHISPER_VOCABULARY", str(CONFIG_DIR / "vocabulary.txt"))
).expanduser()


class Tray:
    def __init__(self) -> None:
        self.current_status = "starting"
        self.icon = Gtk.StatusIcon.new_from_icon_name(ICON_READY)
        self.icon.set_title("Local Whisper Dictation")
        self.icon.set_tooltip_text("Local Whisper Dictation - starting")
        self.icon.set_visible(True)
        self.icon.connect("popup-menu", self._popup_menu)

    def set_status(self, status: str) -> None:
        normalized = status.lower()
        self.current_status = normalized
        if normalized in {"listening", "recording", "busy"}:
            icon_name = ICON_ACTIVE
            tooltip = f"Local Whisper Dictation - {normalized}"
        elif normalized in {"loading", "starting"}:
            icon_name = ICON_READY
            tooltip = "Local Whisper Dictation - loading model"
        elif normalized in {"error", "clipboard error"}:
            icon_name = ICON_ERROR
            tooltip = "Local Whisper Dictation - error"
        elif normalized in {"transcribing", "thinking", "finishing", "pasting", "pasted", "copied"}:
            icon_name = ICON_ACTIVE
            tooltip = f"Local Whisper Dictation - {normalized}"
        else:
            icon_name = ICON_READY
            tooltip = "Local Whisper Dictation - ready"
        self.icon.set_from_icon_name(icon_name)
        self.icon.set_tooltip_text(tooltip)

    def _popup_menu(self, icon, button: int, activate_time: int) -> None:
        menu = Gtk.Menu()
        status = Gtk.MenuItem(label="Local Whisper Dictation")
        status.set_sensitive(False)
        menu.append(status)
        current = Gtk.MenuItem(label=f"Status: {self.current_status}")
        current.set_sensitive(False)
        menu.append(current)
        hotkey = Gtk.MenuItem(label="Hotkey: left Ctrl + left Windows")
        hotkey.set_sensitive(False)
        menu.append(hotkey)
        menu.append(Gtk.SeparatorMenuItem())
        vocabulary = Gtk.MenuItem(label="Open vocabulary")
        vocabulary.connect("activate", self._open_vocabulary)
        menu.append(vocabulary)
        logs = Gtk.MenuItem(label="Open logs")
        logs.connect("activate", self._open_logs)
        menu.append(logs)
        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)

    def _open_vocabulary(self, *_args) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        VOCABULARY_PATH.touch(exist_ok=True)
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(VOCABULARY_PATH)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_logs(self, *_args) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(STATE_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_stdin(tray: Tray) -> None:
    for line in sys.stdin:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        status = str(event.get("status", "ready"))
        GLib.idle_add(tray.set_status, status)
    GLib.idle_add(Gtk.main_quit)


def main() -> None:
    tray = Tray()
    threading.Thread(target=read_stdin, args=(tray,), name="tray-stdin", daemon=True).start()
    Gtk.main()


if __name__ == "__main__":
    main()
