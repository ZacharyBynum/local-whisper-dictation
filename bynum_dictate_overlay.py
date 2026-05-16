#!/usr/bin/env python3
import base64
import contextlib
import json
import math
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from Xlib import display
from Xlib.ext import shape

WIDTH = 196
HEIGHT = 48
BAR_COUNT = 5
RADIUS = 24
BG = "#111111"
FALLBACK_FONT_FAMILY = "helvetica"
BAR_PATTERN = (0.34, 0.72, 1.0, 0.76, 0.42)
BAR_WIDTH = 6
BAR_SPACING = 11
BAR_X = 124
BAR_FILLS = ("#4285f4", "#ea4335", "#fbbc04", "#34a853", "#4285f4")
APP_DIR = pathlib.Path(os.environ.get("BYNUM_DICTATE_APP_DIR", str(pathlib.Path(__file__).resolve().parent))).expanduser()
TEXT_RENDERER = APP_DIR / "bynum_dictate_text_render.py"
TEXT_RENDER_PYTHON = os.environ.get("BYNUM_DICTATE_TEXT_RENDER_PYTHON", "/usr/bin/python3")
RESTART_COMMAND = pathlib.Path(os.environ.get("BYNUM_DICTATE_RESTART_COMMAND", "~/.local/bin/bynum-dictate-restart")).expanduser()
STATUS_IMAGE_WIDTH = 84
STATUS_IMAGE_HEIGHT = 24
SHOWN_ALPHA = 1.0
ANIMATION_MS = int(os.environ.get("BYNUM_DICTATE_OVERLAY_ANIMATION_MS", "75"))
ANIMATION_FRAME_MS = 16
ANIMATION_OFFSET = int(os.environ.get("BYNUM_DICTATE_OVERLAY_ANIMATION_OFFSET", "10"))
RENDER_INTERVAL_MS = int(os.environ.get("BYNUM_DICTATE_OVERLAY_RENDER_MS", "8"))
IDLE_INTERVAL_MS = int(os.environ.get("BYNUM_DICTATE_OVERLAY_IDLE_MS", "16"))
LEVEL_STARTUP_DAMPEN_MS = int(os.environ.get("BYNUM_DICTATE_LEVEL_STARTUP_DAMPEN_MS", "240"))
STATUS_LABELS = (
    "Listening",
    "Busy",
    "Loading",
    "Stopping",
    "Thinking",
    "Pasting",
    "Pasted",
    "Copied",
    "No speech",
    "Too short",
    "Clipboard error",
    "Error",
)
LEVEL_FLOOR = 0.045
LEVEL_CEILING = 0.92
DEFAULT_TEXT_COLOR = "#f8fafc"
ERROR_TEXT_COLOR = "#ff8b8b"
STICKY_FILL = "#f8fafc"
STICKY_BG = "#1b1b1b"
STICKY_OUTLINE = "#4b5563"
STICKY_PULSE = "#6b7280"
STICKY_DIVIDER = "#2a2f36"
RESTART_STATUSES = {"Busy", "Stopping", "Thinking", "Pasting", "Clipboard error", "Error"}


def warn(message: str) -> None:
    print(f"bynum-dictate-overlay: {message}", file=sys.stderr, flush=True)


def display_status(raw_status: object) -> str:
    return {
        "Finishing": "Stopping",
        "Transcribing": "Thinking",
        "Pasting": "Pasting",
        "Pasted": "Pasted",
        "Copied": "Copied",
        "No Speech": "No speech",
        "Too Short": "Too short",
        "Clipboard Error": "Clipboard error",
        "Busy": "Busy",
        "Loading": "Loading",
        "Ready": "Listening",
        "Error": "Error",
        "Listening": "Listening",
    }.get(str(raw_status), str(raw_status or "Working"))


def primary_monitor_geometry() -> tuple[int, int, int, int] | None:
    try:
        result = subprocess.run(["xrandr", "--query"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    except Exception:
        return None

    first_connected = None
    for line in result.stdout.splitlines():
        if " connected " not in line:
            continue
        match = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", line)
        if not match:
            continue
        width, height, x, y = (int(value) for value in match.groups())
        geometry = (x, y, width, height)
        if first_connected is None:
            first_connected = geometry
        if " primary " in line:
            return geometry
    return first_connected


def rounded_shape_rects(width: int, height: int, radius: int) -> list[tuple[int, int, int, int]]:
    rects = []
    r = min(radius, width // 2, height // 2)
    for y in range(height):
        if y < r:
            dy = r - y - 0.5
        elif y >= height - r:
            dy = y - (height - r) + 0.5
        else:
            dy = 0

        inset = int(max(0, r - (r * r - dy * dy) ** 0.5)) if dy else 0
        rects.append((inset, y, width - inset * 2, 1))
    return rects


def apply_rounded_window_shape(root: tk.Tk) -> None:
    dpy = None
    try:
        dpy = display.Display()
        window = dpy.create_resource_object("window", root.winfo_id())
        rects = rounded_shape_rects(WIDTH, HEIGHT, RADIUS)
        window.shape_rectangles(shape.SO.Set, shape.SK.Bounding, 0, 0, 0, rects)
        window.shape_rectangles(shape.SO.Set, shape.SK.Clip, 0, 0, 0, rects)
        dpy.sync()
    except Exception as exc:
        warn(f"rounded window shape unavailable: {exc!r}")
    finally:
        if dpy is not None:
            dpy.close()


def render_status_photo(text: str, color: str = DEFAULT_TEXT_COLOR) -> tk.PhotoImage | None:
    payload = {
        "text": text,
        "width": STATUS_IMAGE_WIDTH,
        "height": STATUS_IMAGE_HEIGHT,
        "size": 13,
        "color": color,
    }
    try:
        result = subprocess.run(
            [TEXT_RENDER_PYTHON, str(TEXT_RENDERER)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=1.0,
            check=True,
        )
        encoded = base64.b64encode(result.stdout).decode("ascii")
        return tk.PhotoImage(data=encoded, format="png")
    except Exception as exc:
        detail = ""
        if "result" in locals() and result.stderr:
            detail = ": " + result.stderr.decode("utf-8", "ignore").strip()
        warn(f"text render failed for {text!r}: {exc!r}{detail}")
        return None


def main() -> None:
    events: queue.Queue[dict] = queue.Queue()
    geometry = primary_monitor_geometry()
    visible = False
    target_bars = [0.08] * BAR_COUNT
    current_bars = [0.08] * BAR_COUNT
    status_text = "Listening"
    status_color = DEFAULT_TEXT_COLOR
    sticky_active = False
    listening_started = 0.0

    def read_stdin() -> None:
        for line in sys.stdin:
            try:
                events.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        events.put({"type": "quit"})

    threading.Thread(target=read_stdin, name="overlay-stdin", daemon=True).start()

    root = tk.Tk()
    root.title("Bynum Dictate Overlay")
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", SHOWN_ALPHA)
    root.configure(bg=BG)
    with contextlib.suppress(tk.TclError):
        root.wm_attributes("-type", "notification")

    status_photo_cache: dict[tuple[str, str], tk.PhotoImage] = {}

    def status_photo_for(text: str, color: str = DEFAULT_TEXT_COLOR) -> tk.PhotoImage | None:
        key = (text, color)
        if key not in status_photo_cache:
            photo = render_status_photo(text, color)
            if photo is not None:
                status_photo_cache[key] = photo
        return status_photo_cache.get(key)

    for label in STATUS_LABELS:
        status_photo_for(label)

    canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill=BG, outline="")
    status_photo = status_photo_for(status_text, status_color)
    status_image = canvas.create_image(20, HEIGHT // 2, anchor="w", image=status_photo, state="normal" if status_photo else "hidden")
    fallback_status = canvas.create_text(
        20,
        HEIGHT // 2,
        anchor="w",
        fill=status_color,
        font=(FALLBACK_FONT_FAMILY, 13, "normal"),
        text=status_text,
        state="hidden" if status_photo else "normal",
    )
    rendered_status_text = status_text
    rendered_status_color = status_color

    bar_items = []
    center_y = HEIGHT // 2
    sticky_items = []
    restart_items = []

    def create_bar(x: int, height: int, color: str) -> int:
        y1 = center_y - height // 2
        y2 = center_y + height // 2
        return canvas.create_line(
            x,
            y1,
            x,
            y2,
            fill=color,
            width=BAR_WIDTH,
            capstyle=tk.ROUND,
        )

    sticky_items.append(canvas.create_oval(86, 16, 106, 36, fill=STICKY_BG, outline=STICKY_OUTLINE, width=1, state="hidden"))
    sticky_items.append(canvas.create_oval(90, 20, 102, 32, outline=STICKY_PULSE, width=1, state="hidden"))
    sticky_items.append(canvas.create_arc(92, 19, 100, 29, start=0, extent=180, style=tk.ARC, outline=STICKY_FILL, width=1, state="hidden"))
    sticky_items.append(canvas.create_rectangle(91, 25, 101, 31, fill=STICKY_FILL, outline="", state="hidden"))
    sticky_items.append(canvas.create_rectangle(95, 28, 97, 31, fill=STICKY_BG, outline="", state="hidden"))
    sticky_items.append(canvas.create_line(115, 17, 115, 31, fill=STICKY_DIVIDER, width=1, state="hidden"))

    for index in range(BAR_COUNT):
        bar_items.append(create_bar(BAR_X + index * BAR_SPACING, 8, BAR_FILLS[index]))

    restart_hit = canvas.create_oval(176, 14, 194, 34, fill=BG, outline="", state="hidden", tags=("restart",))
    restart_items.append(restart_hit)
    restart_items.append(
        canvas.create_oval(177, 15, 193, 33, fill="#151820", outline="#303640", width=1, state="hidden", tags=("restart",))
    )
    restart_items.append(
        canvas.create_arc(181, 19, 189, 27, start=35, extent=285, style=tk.ARC, outline="#d8dde5", width=2, state="hidden", tags=("restart",))
    )
    restart_items.append(canvas.create_line(188, 18, 190, 22, 186, 21, fill="#d8dde5", width=1, state="hidden", tags=("restart",)))

    def restart_with_confirmation(_event=None) -> None:
        if not RESTART_COMMAND.exists():
            warn(f"restart command not found: {RESTART_COMMAND}")
            return
        root.lift()
        confirmed = messagebox.askyesno(
            "Restart Bynum Dictate?",
            "Restart the dictation background service?",
            parent=root,
        )
        if not confirmed:
            return
        try:
            subprocess.Popen([str(RESTART_COMMAND)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as exc:
            warn(f"restart command failed: {exc!r}")

    canvas.tag_bind("restart", "<Button-1>", restart_with_confirmation)
    canvas.tag_bind("restart", "<Enter>", lambda _event: canvas.configure(cursor="hand2"))
    canvas.tag_bind("restart", "<Leave>", lambda _event: canvas.configure(cursor=""))

    hide_after_id = None
    animation_after_id = None
    base_position = (0, 0)
    window_x = 0
    window_y = 0
    window_alpha = SHOWN_ALPHA

    def target_position() -> tuple[int, int]:
        nonlocal geometry
        if geometry is None:
            geometry = primary_monitor_geometry()
        if geometry:
            monitor_x, monitor_y, monitor_w, monitor_h = geometry
            x = monitor_x + max(0, int((monitor_w - WIDTH) / 2))
            y = monitor_y + max(0, monitor_h - HEIGHT - 84)
        else:
            x = max(0, int((root.winfo_screenwidth() - WIDTH) / 2))
            y = max(0, root.winfo_screenheight() - HEIGHT - 84)
        return x, y

    def set_window(x: int, y: int, alpha: float) -> None:
        nonlocal window_x, window_y, window_alpha
        window_x = x
        window_y = y
        window_alpha = max(0.0, min(SHOWN_ALPHA, alpha))
        root.geometry(f"{WIDTH}x{HEIGHT}+{window_x}+{window_y}")
        with contextlib.suppress(tk.TclError):
            root.attributes("-alpha", window_alpha)

    def cancel_animation() -> None:
        nonlocal animation_after_id
        if animation_after_id is not None:
            root.after_cancel(animation_after_id)
            animation_after_id = None

    def animate_window(end_x: int, end_y: int, end_alpha: float, mode: str, done=None) -> None:
        nonlocal animation_after_id
        cancel_animation()
        if ANIMATION_MS <= 0:
            set_window(end_x, end_y, end_alpha)
            if done is not None:
                done()
            return

        start_x = window_x
        start_y = window_y
        start_alpha = window_alpha
        started = time.monotonic()

        def ease(progress: float) -> float:
            if mode == "in":
                return progress * progress * progress
            return 1 - (1 - progress) ** 3

        def step() -> None:
            nonlocal animation_after_id
            progress = min(1.0, (time.monotonic() - started) * 1000 / ANIMATION_MS)
            eased = ease(progress)
            next_x = int(round(start_x + (end_x - start_x) * eased))
            next_y = int(round(start_y + (end_y - start_y) * eased))
            next_alpha = start_alpha + (end_alpha - start_alpha) * eased
            set_window(next_x, next_y, next_alpha)
            if progress < 1.0:
                animation_after_id = root.after(ANIMATION_FRAME_MS, step)
            else:
                animation_after_id = None
                set_window(end_x, end_y, end_alpha)
                if done is not None:
                    done()

        step()

    def show(lift: bool = True) -> None:
        nonlocal base_position, hide_after_id, visible
        if hide_after_id is not None:
            root.after_cancel(hide_after_id)
            hide_after_id = None
        base_position = target_position()
        base_x, base_y = base_position
        if not visible:
            cancel_animation()
            set_window(base_x, base_y + ANIMATION_OFFSET, 0.0)
            root.update_idletasks()
            apply_rounded_window_shape(root)
            root.deiconify()
            root.after_idle(lambda: apply_rounded_window_shape(root))
            visible = True
            lift = True
        if lift:
            root.lift()
        if abs(window_y - base_y) > 1 or abs(window_x - base_x) > 1 or window_alpha < SHOWN_ALPHA * 0.98:
            animate_window(base_x, base_y, SHOWN_ALPHA, "out")

    def hide() -> None:
        nonlocal hide_after_id, visible
        hide_after_id = None
        if not visible:
            return

        def finish_hide() -> None:
            nonlocal visible
            root.withdraw()
            visible = False
            with contextlib.suppress(tk.TclError):
                root.attributes("-alpha", SHOWN_ALPHA)

        base_x, base_y = base_position
        animate_window(base_x, base_y + ANIMATION_OFFSET, 0.0, "in", finish_hide)

    def render() -> None:
        nonlocal rendered_status_text, rendered_status_color, status_photo
        if status_text != rendered_status_text or status_color != rendered_status_color:
            next_photo = status_photo_for(status_text, status_color)
            if next_photo is not None:
                status_photo = next_photo
                canvas.itemconfig(status_image, image=status_photo, state="normal")
                canvas.itemconfig(fallback_status, state="hidden")
            else:
                canvas.itemconfig(status_image, state="hidden")
                canvas.itemconfig(fallback_status, text=status_text, fill=status_color, state="normal")
            rendered_status_text = status_text
            rendered_status_color = status_color
        for index, (bar, level) in enumerate(zip(bar_items, current_bars, strict=False)):
            shaped = max(LEVEL_FLOOR, min(LEVEL_CEILING, level))
            height = max(BAR_WIDTH, int(34 * shaped))
            x = canvas.coords(bar)[0]
            y1 = center_y - height // 2
            y2 = center_y + height // 2
            canvas.coords(bar, x, y1, x, y2)
            canvas.itemconfig(bar, fill=BAR_FILLS[index], width=BAR_WIDTH, capstyle=tk.ROUND)
        if sticky_active:
            pulse = (math.sin(time.monotonic() * 5.0) + 1.0) / 2.0
            pulse_radius = 5.4 + pulse * 1.4
            center_x = 96
            center_y_icon = HEIGHT // 2
            canvas.coords(
                sticky_items[1],
                center_x - pulse_radius,
                center_y_icon - pulse_radius,
                center_x + pulse_radius,
                center_y_icon + pulse_radius,
            )
            for item in sticky_items:
                canvas.itemconfig(item, state="normal")
        else:
            for item in sticky_items:
                canvas.itemconfig(item, state="hidden")
        restart_state = "normal" if status_text in RESTART_STATUSES else "hidden"
        for item in restart_items:
            canvas.itemconfig(item, state=restart_state)

    def process() -> None:
        nonlocal hide_after_id, target_bars, current_bars, status_text, status_color, sticky_active, listening_started
        last_level = None
        try:
            while True:
                event = events.get_nowait()
                kind = event.get("type")
                if kind == "quit":
                    root.destroy()
                    return
                if kind == "show":
                    status_text = display_status(event.get("status", "Listening"))
                    status_color = ERROR_TEXT_COLOR if status_text == "Error" else DEFAULT_TEXT_COLOR
                    target_bars = [LEVEL_FLOOR] * BAR_COUNT
                    current_bars = [LEVEL_FLOOR] * BAR_COUNT
                    if status_text == "Listening":
                        listening_started = time.monotonic()
                    show()
                    render()
                elif kind == "status":
                    status_text = display_status(event.get("status", "Working"))
                    status_color = DEFAULT_TEXT_COLOR
                    if status_text in {"No speech", "Too short", "Clipboard error", "Error"}:
                        status_color = ERROR_TEXT_COLOR
                    show()
                    render()
                elif kind == "level":
                    last_level = event
                elif kind == "sticky":
                    sticky_active = bool(event.get("active"))
                    if sticky_active:
                        show()
                    render()
                elif kind == "hide":
                    delay = int(event.get("delay_ms", 0))
                    if delay:
                        hide_after_id = root.after(delay, hide)
                    else:
                        hide()

            # Unreachable, but keeps static analyzers happy.
        except queue.Empty:
            pass

        if last_level is not None:
            level = max(0.0, min(LEVEL_CEILING, float(last_level.get("level", 0))))
            raw_bars = last_level.get("bars")
            if isinstance(raw_bars, list) and raw_bars:
                next_bars = [max(0.0, min(LEVEL_CEILING, float(value))) for value in raw_bars[:BAR_COUNT]]
                while len(next_bars) < BAR_COUNT:
                    next_bars.append(level)
                target_bars = [
                    max(LEVEL_FLOOR, min(LEVEL_CEILING, LEVEL_FLOOR + (value - LEVEL_FLOOR) * factor))
                    for value, factor in zip(next_bars, BAR_PATTERN, strict=False)
                ]
            else:
                target_bars = [max(LEVEL_FLOOR, min(LEVEL_CEILING, level * factor)) for factor in BAR_PATTERN]
            if LEVEL_STARTUP_DAMPEN_MS > 0 and status_text == "Listening" and listening_started:
                elapsed_ms = (time.monotonic() - listening_started) * 1000
                if elapsed_ms < LEVEL_STARTUP_DAMPEN_MS:
                    scale = max(0.0, min(1.0, elapsed_ms / LEVEL_STARTUP_DAMPEN_MS))
                    target_bars = [LEVEL_FLOOR + (value - LEVEL_FLOOR) * scale for value in target_bars]
            show(lift=False)

        if visible:
            updated = []
            for current, target in zip(current_bars, target_bars, strict=False):
                if target > current:
                    updated.append(current * 0.84 + target * 0.16)
                else:
                    updated.append(current * 0.90 + target * 0.10)
            current_bars = updated
            render()

        root.after(max(1, RENDER_INTERVAL_MS if visible else IDLE_INTERVAL_MS), process)

    process()
    root.mainloop()


if __name__ == "__main__":
    main()
