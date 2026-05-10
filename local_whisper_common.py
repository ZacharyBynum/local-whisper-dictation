#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import time
from collections.abc import Callable

APP_DIR = pathlib.Path(
    os.environ.get("LOCAL_WHISPER_APP_DIR", str(pathlib.Path(__file__).resolve().parent))
).expanduser()
CONFIG_DIR = pathlib.Path(os.environ.get("LOCAL_WHISPER_CONFIG_DIR", "~/.config/local-whisper")).expanduser()
STATE_DIR = pathlib.Path(os.environ.get("LOCAL_WHISPER_STATE_DIR", "~/.local/state/local-whisper")).expanduser()
MODEL_CACHE = pathlib.Path(os.environ.get("LOCAL_WHISPER_MODEL_CACHE", str(APP_DIR / "models"))).expanduser()
DEFAULT_VOCABULARY = pathlib.Path(
    os.environ.get("LOCAL_WHISPER_VOCABULARY", str(CONFIG_DIR / "vocabulary.txt"))
).expanduser()

TERMINAL_HINTS = {
    "alacritty",
    "blackbox",
    "console",
    "contour",
    "cool-retro-term",
    "deepin-terminal",
    "eterm",
    "foot",
    "ghostty",
    "gnome-console",
    "gnome-terminal",
    "guake",
    "hyper",
    "kgx",
    "kitty",
    "konsole",
    "lxterminal",
    "mate-terminal",
    "mlterm",
    "org.gnome.console",
    "org.gnome.terminal",
    "ptyxis",
    "qterminal",
    "roxterm",
    "st-256color",
    "terminator",
    "terminology",
    "tilix",
    "urxvt",
    "wezterm",
    "xfce4-terminal",
    "xterm",
}

Logger = Callable[[str], None]
CLIPBOARD_READY_TIMEOUT = float(os.environ.get("LOCAL_WHISPER_CLIPBOARD_READY_TIMEOUT", "0.25"))


def load_vocabulary(
    path: pathlib.Path = DEFAULT_VOCABULARY,
    *,
    max_chars: int = 1800,
    logger: Logger | None = None,
) -> tuple[str | None, int]:
    try:
        raw_lines = path.expanduser().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None, 0
    except Exception as exc:
        if logger is not None:
            logger(f"vocabulary load failed: {exc!r}")
        return None, 0

    terms = []
    seen = set()
    for raw_line in raw_lines:
        term = raw_line.split("#", 1)[0].strip()
        if not term:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)

    if not terms:
        return None, 0

    text = ", ".join(terms)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(",", 1)[0].strip()
    return text, len(terms)


def copy_to_clipboard(text: str, logger: Logger | None = None) -> bool:
    if not text:
        return False

    commands = []
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        commands.append(["wl-copy"])
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        commands.append(["xclip", "-selection", "clipboard"])

    for command in commands:
        proc = None
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            assert proc.stdin is not None
            proc.stdin.write(text)
            proc.stdin.close()
        except Exception as exc:
            if logger is not None:
                logger(f"clipboard command failed to start ({command[0]}): {exc!r}")
            if proc is not None and proc.poll() is None:
                proc.kill()
            continue

        try:
            returncode = proc.wait(timeout=CLIPBOARD_READY_TIMEOUT)
        except subprocess.TimeoutExpired:
            return True
        if returncode == 0:
            return True
        if logger is not None:
            logger(f"clipboard command failed ({command[0]} exit {returncode})")
    return False


def active_window_id(logger: Logger | None = None) -> int | None:
    if not os.environ.get("DISPLAY"):
        return None
    dpy = None
    try:
        from Xlib import X, display

        dpy = display.Display()
        root = dpy.screen().root
        active_atom = dpy.intern_atom("_NET_ACTIVE_WINDOW")
        prop = root.get_full_property(active_atom, X.AnyPropertyType)
        if prop is not None and len(prop.value):
            return int(prop.value[0])
        focus = dpy.get_input_focus().focus
        return getattr(focus, "id", None)
    except Exception as exc:
        if logger is not None:
            logger(f"active window lookup failed: {exc!r}")
        return None
    finally:
        if dpy is not None:
            dpy.close()


def window_text_property(dpy, window, name: str) -> str:
    try:
        atom = dpy.intern_atom(name)
        prop = window.get_full_property(atom, dpy.intern_atom("UTF8_STRING"))
        if prop is not None:
            value = prop.value
            if isinstance(value, bytes):
                return value.decode("utf-8", "ignore")
            return bytes(value).decode("utf-8", "ignore")
    except Exception:
        pass
    return ""


def is_terminal_window(window_id: int | None, logger: Logger | None = None) -> bool:
    if not window_id or not os.environ.get("DISPLAY"):
        return False
    dpy = None
    try:
        from Xlib import display

        dpy = display.Display()
        window = dpy.create_resource_object("window", window_id)
        wm_class = window.get_wm_class() or ()
        name = window.get_wm_name() or window_text_property(dpy, window, "_NET_WM_NAME")
        haystack = " ".join(str(part).lower() for part in (*wm_class, name))
        return any(hint in haystack for hint in TERMINAL_HINTS)
    except Exception as exc:
        if logger is not None:
            logger(f"terminal detection failed for {window_id}: {exc!r}")
        return False
    finally:
        if dpy is not None:
            dpy.close()


def paste_x11(
    window_id: int | None = None,
    *,
    terminal_aware: bool = True,
    logger: Logger | None = None,
) -> bool:
    if not os.environ.get("DISPLAY"):
        return False

    dpy = None
    try:
        from Xlib import XK, X, display
        from Xlib.ext import xtest

        if window_id is None:
            window_id = active_window_id(logger)

        dpy = display.Display()
        use_terminal_paste = terminal_aware and is_terminal_window(window_id, logger)
        if window_id:
            try:
                target = dpy.create_resource_object("window", window_id)
                target.set_input_focus(X.RevertToParent, X.CurrentTime)
                dpy.sync()
                time.sleep(0.08)
            except Exception as exc:
                if logger is not None:
                    logger(f"could not restore focus to {window_id}: {exc!r}")

        ctrl = dpy.keysym_to_keycode(XK.string_to_keysym("Control_L"))
        shift = dpy.keysym_to_keycode(XK.string_to_keysym("Shift_L"))
        v_key = dpy.keysym_to_keycode(XK.string_to_keysym("v"))
        if not ctrl or not v_key or (use_terminal_paste and not shift):
            return False

        xtest.fake_input(dpy, X.KeyPress, ctrl)
        if use_terminal_paste:
            xtest.fake_input(dpy, X.KeyPress, shift)
        xtest.fake_input(dpy, X.KeyPress, v_key)
        xtest.fake_input(dpy, X.KeyRelease, v_key)
        if use_terminal_paste:
            xtest.fake_input(dpy, X.KeyRelease, shift)
        xtest.fake_input(dpy, X.KeyRelease, ctrl)
        dpy.sync()
        return True
    except Exception as exc:
        if logger is not None:
            logger(f"paste failed: {exc!r}")
        return False
    finally:
        if dpy is not None:
            dpy.close()
