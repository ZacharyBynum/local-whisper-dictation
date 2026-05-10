import pathlib
import subprocess

import bynum_dictate_common as common
import bynum_dictate_once
import bynum_dictate_restart


def test_load_vocabulary_deduplicates_comments_and_caps_length(tmp_path):
    vocabulary = tmp_path / "vocabulary.txt"
    vocabulary.write_text(
        "\n".join(
            [
                "# comment",
                "CTranslate2",
                "ctranslate2 # duplicate with different case",
                "",
                "faster-whisper",
                "Bynum Dictate",
            ]
        ),
        encoding="utf-8",
    )

    text, count = common.load_vocabulary(vocabulary, max_chars=40)

    assert count == 3
    assert text == "CTranslate2, faster-whisper"


def test_load_vocabulary_missing_file_returns_empty(tmp_path):
    text, count = common.load_vocabulary(tmp_path / "missing.txt")

    assert text is None
    assert count == 0


def test_copy_to_clipboard_returns_true_when_xclip_keeps_owning_clipboard(monkeypatch):
    class FakeStdin:
        def __init__(self):
            self.value = ""
            self.closed = False

        def write(self, value):
            self.value += value

        def close(self):
            self.closed = True

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.stdin = FakeStdin()

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="xclip", timeout=timeout)

        def poll(self):
            return None

        def kill(self):
            raise AssertionError("long-lived clipboard owner should not be killed")

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(common.shutil, "which", lambda command: "/usr/bin/xclip" if command == "xclip" else None)
    monkeypatch.setattr(common.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(common, "CLIPBOARD_READY_TIMEOUT", 0.01)

    assert common.copy_to_clipboard("hello") is True


def test_copy_to_clipboard_tries_next_command_after_start_failure(monkeypatch):
    calls = []

    class FakeStdin:
        def write(self, value):
            self.value = value

        def close(self):
            self.closed = True

    class FakeProcess:
        def __init__(self, command, **kwargs):
            calls.append(command[0])
            if command[0] == "wl-copy":
                raise OSError("broken wayland clipboard")
            self.stdin = FakeStdin()

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    messages = []
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(common.shutil, "which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(common.subprocess, "Popen", FakeProcess)

    assert common.copy_to_clipboard("fallback", messages.append) is True
    assert calls == ["wl-copy", "xclip"]
    assert any("wl-copy" in message for message in messages)


def test_active_window_id_without_display_returns_none(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)

    assert common.active_window_id() is None


def test_is_terminal_window_without_window_returns_false(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")

    assert common.is_terminal_window(None) is False


def test_project_docs_exist():
    root = pathlib.Path(__file__).resolve().parents[1]

    for filename in ["README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "pyproject.toml"]:
        assert (root / filename).exists()


def test_dictate_wrapper_builds_record_paste_notify_args():
    assert bynum_dictate_once.build_args(["--seconds", "2"]) == ["record", "--paste", "--notify", "--seconds", "2"]


def test_restart_command_target_detection(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    target = app_dir / "bynum_dictate_hotkey.py"
    target.write_text("# hotkey", encoding="utf-8")

    assert bynum_dictate_restart.command_targets_app(["python", str(target)], app_dir)
    assert not bynum_dictate_restart.command_targets_app(["python", str(app_dir / "bynum_dictate_restart.py")], app_dir)
    assert not bynum_dictate_restart.command_targets_app(["python", "/tmp/bynum_dictate_hotkey.py"], app_dir)


def test_restart_target_pids_reads_proc_style_cmdline(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    hotkey = app_dir / "bynum_dictate_hotkey.py"
    hotkey.write_text("# hotkey", encoding="utf-8")
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    current = proc_root / str(bynum_dictate_restart.os.getpid())
    current.mkdir()
    (current / "cmdline").write_bytes(f"python\0{hotkey}\0".encode())
    target = proc_root / "123"
    target.mkdir()
    (target / "cmdline").write_bytes(f"python\0{hotkey}\0".encode())
    unrelated = proc_root / "456"
    unrelated.mkdir()
    (unrelated / "cmdline").write_bytes(b"python\0elsewhere.py\0")

    assert bynum_dictate_restart.target_pids(app_dir, proc_root) == [123]
