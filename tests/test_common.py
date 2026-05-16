import pathlib
import subprocess
from types import SimpleNamespace

import bynum_dictate
import bynum_dictate_common as common
import bynum_dictate_hotkey
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


def test_hotkey_state_machine_normal_hold_to_dictate():
    state = bynum_dictate_hotkey.HotkeyStateMachine(max_record_seconds=45)

    assert state.update(ctrl_down=True, super_down=True, space_down=False, now=1.0)[0] == ["start_normal"]
    assert state.update(ctrl_down=True, super_down=True, space_down=False, now=1.2)[0] == []
    assert state.update(ctrl_down=False, super_down=False, space_down=False, now=1.5)[0] == ["stop_normal"]


def test_hotkey_state_machine_space_latches_active_recording_until_space_pressed_again():
    state = bynum_dictate_hotkey.HotkeyStateMachine(max_record_seconds=45)

    assert state.update(ctrl_down=True, super_down=True, space_down=False, now=1.0)[0] == ["start_normal"]
    assert state.update(ctrl_down=True, super_down=True, space_down=True, now=1.1)[0] == ["enable_sticky"]
    assert state.update(ctrl_down=False, super_down=False, space_down=True, now=1.2)[0] == []
    assert state.update(ctrl_down=False, super_down=False, space_down=False, now=1.3)[0] == []
    assert state.update(ctrl_down=False, super_down=False, space_down=True, now=1.4)[0] == ["stop_sticky"]


def test_hotkey_state_machine_can_start_sticky_with_chord_and_space_together():
    state = bynum_dictate_hotkey.HotkeyStateMachine(max_record_seconds=45)

    assert state.update(ctrl_down=True, super_down=True, space_down=True, now=1.0)[0] == ["start_sticky"]
    assert state.update(ctrl_down=False, super_down=False, space_down=False, now=1.1)[0] == []
    assert state.update(ctrl_down=True, super_down=True, space_down=False, now=1.2)[0] == ["stop_sticky"]


def test_hotkey_state_machine_does_not_auto_stop_sticky_recording():
    state = bynum_dictate_hotkey.HotkeyStateMachine(max_record_seconds=2)

    assert state.update(ctrl_down=True, super_down=True, space_down=True, now=1.0)[0] == ["start_sticky"]
    assert state.update(ctrl_down=False, super_down=False, space_down=False, now=1.1)[0] == []
    assert state.update(ctrl_down=False, super_down=False, space_down=False, now=10.0)[0] == []


def test_model_manager_falls_back_to_cpu_when_cuda_load_fails(monkeypatch):
    class FakeTray:
        def status(self, _status):
            pass

    class FakeModel:
        def __init__(self, _name, *, device, compute_type, **_kwargs):
            calls.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("CUDA failed with error no CUDA-capable device is detected")

    calls = []
    monkeypatch.setenv("BYNUM_DICTATE_PRELOAD", "0")
    monkeypatch.setattr(bynum_dictate_hotkey, "WhisperModel", FakeModel)
    monkeypatch.setattr(bynum_dictate_hotkey, "DEVICE", "cuda")
    monkeypatch.setattr(bynum_dictate_hotkey, "COMPUTE_TYPE", "float16")
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK", True)
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK_MODEL", "base.en")
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK_COMPUTE", "int8")

    manager = bynum_dictate_hotkey.ModelManager(None, FakeTray())

    assert isinstance(manager.get(), FakeModel)
    assert calls == [("cuda", "float16"), ("cpu", "int8")]
    assert manager.model_name == "base.en"
    assert manager.device == "cpu"


def test_transcribe_retries_on_cpu_when_cuda_runtime_fails(monkeypatch, tmp_path):
    class FakeTray:
        def status(self, _status):
            pass

    class FakeSegment:
        text = " fixed"

    class FakeModel:
        def __init__(self, _name, *, device, compute_type, **_kwargs):
            self.device = device
            calls.append((device, compute_type))

        def transcribe(self, *_args, **_kwargs):
            if self.device == "cuda":
                raise RuntimeError("CUDA failed with error no CUDA-capable device is detected")
            return [FakeSegment()], object()

    calls = []
    monkeypatch.setenv("BYNUM_DICTATE_PRELOAD", "0")
    monkeypatch.setattr(bynum_dictate_hotkey, "WhisperModel", FakeModel)
    monkeypatch.setattr(bynum_dictate_hotkey, "DEVICE", "cuda")
    monkeypatch.setattr(bynum_dictate_hotkey, "COMPUTE_TYPE", "float16")
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK", True)
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK_MODEL", "base.en")
    monkeypatch.setattr(bynum_dictate_hotkey, "CPU_FALLBACK_COMPUTE", "int8")
    monkeypatch.setattr(bynum_dictate_hotkey, "AUDIO_PREP", False)

    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"placeholder")
    manager = bynum_dictate_hotkey.ModelManager(None, FakeTray())
    recording = bynum_dictate_hotkey.Recording(audio, None, 1.0, 1.0, 1.0, 10, 10)

    assert bynum_dictate_hotkey.transcribe(recording, manager) == "fixed"
    assert calls == [("cuda", "float16"), ("cpu", "int8")]
    assert manager.model_name == "base.en"
    assert manager.device == "cpu"


def test_one_shot_dictate_model_load_falls_back_to_cpu(monkeypatch):
    class FakeModel:
        def __init__(self, _name, *, device, compute_type, **_kwargs):
            calls.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("CUDA failed with error no CUDA-capable device is detected")

    calls = []
    args = SimpleNamespace(
        model="tiny",
        device="cuda",
        compute_type="float16",
        cpu_fallback=True,
        cpu_model="base.en",
        cpu_compute_type="int8",
        local_only=True,
    )
    monkeypatch.setattr(bynum_dictate, "WhisperModel", FakeModel)

    assert isinstance(bynum_dictate.load_model_with_fallback(args), FakeModel)
    assert calls == [("cuda", "float16"), ("cpu", "int8")]
    assert args.model == "base.en"
    assert args.device == "cpu"


def test_warmup_uses_cpu_fallback(monkeypatch, capsys):
    class FakeModel:
        def __init__(self, _name, *, device, compute_type, **_kwargs):
            calls.append((device, compute_type))
            if device == "cuda":
                raise RuntimeError("CUDA failed with error no CUDA-capable device is detected")

    calls = []
    args = SimpleNamespace(
        model="tiny",
        device="cuda",
        compute_type="float16",
        cpu_fallback=True,
        cpu_model="base.en",
        cpu_compute_type="int8",
        local_only=True,
    )
    monkeypatch.setattr(bynum_dictate, "WhisperModel", FakeModel)

    bynum_dictate.cmd_warmup(args)

    assert calls == [("cuda", "float16"), ("cpu", "int8")]
    assert capsys.readouterr().out.strip() == "Model ready: base.en on cpu/int8"
