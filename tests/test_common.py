import pathlib
import subprocess

import local_whisper_common as common


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
                "Local Whisper",
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
