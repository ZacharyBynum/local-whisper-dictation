#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import os
import pathlib
import signal
import subprocess
import time

from bynum_dictate_common import APP_DIR, STATE_DIR

TARGET_SCRIPTS = frozenset(
    {
        "bynum_dictate_hotkey.py",
        "bynum_dictate_overlay.py",
        "bynum_dictate_tray.py",
    }
)


def command_targets_app(command: list[str], app_dir: pathlib.Path = APP_DIR) -> bool:
    app_dir = app_dir.resolve()
    for part in command:
        try:
            path = pathlib.Path(part).resolve()
        except OSError:
            continue
        if path.parent == app_dir and path.name in TARGET_SCRIPTS:
            return True
    return False


def target_pids(app_dir: pathlib.Path = APP_DIR, proc_root: pathlib.Path = pathlib.Path("/proc")) -> list[int]:
    current_pid = os.getpid()
    pids = []
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name)
        if pid == current_pid:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        command = [part.decode("utf-8", "ignore") for part in raw.split(b"\0") if part]
        if command_targets_app(command, app_dir):
            pids.append(pid)
    return pids


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_targets(pids: list[int], *, wait_seconds: float = 0.6) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if not any(process_is_alive(pid) for pid in pids):
            return
        time.sleep(0.05)

    for pid in pids:
        if not process_is_alive(pid):
            continue
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def start_hotkey(command: list[str], state_dir: pathlib.Path = STATE_DIR) -> subprocess.Popen:
    state_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = state_dir / "hotkey.stderr"
    stderr = stderr_path.open("a", encoding="utf-8")
    try:
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            start_new_session=True,
        )
    finally:
        stderr.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restart the Bynum Dictate background service")
    parser.add_argument("--app-dir", default=str(APP_DIR), help="Bynum Dictate app directory")
    parser.add_argument("--state-dir", default=str(STATE_DIR), help="Bynum Dictate state/log directory")
    parser.add_argument("--hotkey-command", default=str(pathlib.Path.home() / ".local" / "bin" / "bynum-dictate-hotkey"))
    parser.add_argument("--no-start", action="store_true", help="stop existing processes without starting the hotkey daemon")
    parser.add_argument("--wait", type=float, default=0.6, help="seconds to wait before force-killing old processes")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app_dir = pathlib.Path(args.app_dir).expanduser()
    state_dir = pathlib.Path(args.state_dir).expanduser()
    pids = target_pids(app_dir)
    stop_targets(pids, wait_seconds=max(0.0, args.wait))
    if not args.no_start:
        start_hotkey([args.hotkey_command], state_dir)


if __name__ == "__main__":
    main()
