#!/usr/bin/env python3
import array
import contextlib
import fcntl
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

from faster_whisper import WhisperModel
from Xlib import XK, X, display
from Xlib.ext import record
from Xlib.protocol import rq

from bynum_dictate_common import (
    APP_DIR,
    DEFAULT_VOCABULARY,
    MODEL_CACHE,
    STATE_DIR,
    active_window_id,
    copy_to_clipboard,
    load_vocabulary,
    paste_x11,
)

LOG_PATH = STATE_DIR / "hotkey.log"
LOCK_PATH = pathlib.Path(f"/tmp/bynum-dictate-hotkey-{os.getuid()}.lock")
VOCABULARY_PATH = DEFAULT_VOCABULARY
VOCABULARY_MAX_CHARS = int(os.environ.get("BYNUM_DICTATE_VOCABULARY_MAX_CHARS", "1800"))

MODEL_NAME = os.environ.get("BYNUM_DICTATE_MODEL", "distil-large-v3.5")
COMPUTE_TYPE = os.environ.get("BYNUM_DICTATE_COMPUTE", "float16")
LANGUAGE = os.environ.get("BYNUM_DICTATE_LANGUAGE", "en") or None
DEVICE = os.environ.get("BYNUM_DICTATE_DEVICE", "cuda")
BEAM_SIZE = int(os.environ.get("BYNUM_DICTATE_BEAM_SIZE", "3"))
VAD_FILTER = os.environ.get("BYNUM_DICTATE_VAD", "0").lower() not in {"0", "false", "no", "off"}
NO_SPEECH_THRESHOLD = float(os.environ.get("BYNUM_DICTATE_NO_SPEECH_THRESHOLD", "0.45"))
VOICE_THRESHOLD = float(os.environ.get("BYNUM_DICTATE_VOICE_THRESHOLD", "0.012"))
IGNORE_START_MS = int(os.environ.get("BYNUM_DICTATE_IGNORE_START_MS", "360"))
MIN_SPEECH_MS = int(os.environ.get("BYNUM_DICTATE_MIN_SPEECH_MS", "180"))
VISUAL_NOISE_FLOOR = float(os.environ.get("BYNUM_DICTATE_VISUAL_FLOOR", "0.003"))
VISUAL_FLOOR_LEVEL = float(os.environ.get("BYNUM_DICTATE_VISUAL_LEVEL_FLOOR", "0.045"))
VISUAL_CEILING = float(os.environ.get("BYNUM_DICTATE_VISUAL_CEILING", "0.90"))
VISUAL_DB_FLOOR = float(os.environ.get("BYNUM_DICTATE_VISUAL_DB_FLOOR", "-48"))
VISUAL_DB_CEILING = float(os.environ.get("BYNUM_DICTATE_VISUAL_DB_CEILING", "-5"))
VISUAL_BAR_COUNT = 5
AUDIO_PREP = os.environ.get("BYNUM_DICTATE_AUDIO_PREP", "1").lower() not in {"0", "false", "no", "off"}
AUDIO_LEAD_IN_MS = int(os.environ.get("BYNUM_DICTATE_LEAD_IN_MS", "40"))
AUDIO_TAIL_PAD_MS = int(os.environ.get("BYNUM_DICTATE_TAIL_PAD_MS", "40"))
AUDIO_NORMALIZE_PEAK = float(os.environ.get("BYNUM_DICTATE_NORMALIZE_PEAK", "0.86"))
AUDIO_MAX_GAIN = float(os.environ.get("BYNUM_DICTATE_MAX_GAIN", "2.25"))
AUDIO_NORMALIZE_MIN_PEAK = float(os.environ.get("BYNUM_DICTATE_NORMALIZE_MIN_PEAK", "0.025"))
START_TONE_BEFORE_RECORD = os.environ.get("BYNUM_DICTATE_START_TONE_BEFORE_RECORD", "1") != "0"
MAX_RECORD_SECONDS = float(os.environ.get("BYNUM_DICTATE_MAX_SECONDS", "45"))
CHORD_GRACE_SECONDS = float(os.environ.get("BYNUM_DICTATE_CHORD_GRACE", "0.70"))
RETRIGGER_COOLDOWN_SECONDS = float(os.environ.get("BYNUM_DICTATE_RETRIGGER_COOLDOWN", "0.30"))
KEY_POLL_INTERVAL_SECONDS = float(os.environ.get("BYNUM_DICTATE_KEY_POLL_INTERVAL", "0.08"))
LOCAL_FILES_ONLY = os.environ.get("BYNUM_DICTATE_LOCAL_ONLY", "1") != "0"
TRAY_PYTHON = os.environ.get("BYNUM_DICTATE_TRAY_PYTHON", "/usr/bin/python3")
BUSY_NOTICE_MS = int(os.environ.get("BYNUM_DICTATE_BUSY_NOTICE_MS", "650"))
BUSY_STUCK_SECONDS = float(os.environ.get("BYNUM_DICTATE_BUSY_STUCK_SECONDS", "2.0"))
BUSY_STUCK_NOTICE_MS = int(os.environ.get("BYNUM_DICTATE_BUSY_STUCK_NOTICE_MS", "8000"))
SAMPLE_RATE = 16000
TONE_RATE = 44100
SAMPLE_WIDTH = 2
CHANNELS = 1
CHUNK_FRAMES = 800
CHUNK_BYTES = CHUNK_FRAMES * SAMPLE_WIDTH * CHANNELS


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def single_instance() -> object:
    lock = LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0) from None
    lock.write(str(os.getpid()))
    lock.flush()
    return lock


class Overlay:
    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = os.environ.get("BYNUM_DICTATE_OVERLAY", "1") != "0" if enabled is None else enabled
        self.proc: subprocess.Popen | None = None
        self.stderr = None
        if self.enabled:
            try:
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                self.stderr = (STATE_DIR / "overlay.stderr").open("a", encoding="utf-8")
                self.proc = subprocess.Popen(
                    [sys.executable, str(APP_DIR / "bynum_dictate_overlay.py")],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=self.stderr,
                    text=True,
                    bufsize=1,
                )
                log("overlay process started")
            except Exception as exc:
                self.enabled = False
                log(f"overlay disabled: {exc!r}")

    def show(self, status: str, detail: str = "") -> None:
        self._send({"type": "show", "status": status, "detail": detail, "color": "#8ef0a4"})

    def status(self, status: str, detail: str = "") -> None:
        color = "#f0d38e" if status in {"Finishing", "Transcribing", "Pasting"} else "#8ef0a4"
        if status in {"Error", "No Speech", "Too Short", "Clipboard Error"}:
            color = "#ff7f87"
        self._send({"type": "status", "status": status, "detail": detail, "color": color})

    def level(self, value: float, heard: bool, bars: list[float] | None = None) -> None:
        event = {"type": "level", "level": max(0.0, min(1.0, value)), "heard": heard}
        if bars is not None:
            event["bars"] = [max(0.0, min(1.0, bar)) for bar in bars[:VISUAL_BAR_COUNT]]
        self._send(event)

    def hide(self, delay_ms: int = 0) -> None:
        self._send({"type": "hide", "delay_ms": delay_ms})

    def _send(self, event: dict) -> None:
        if not self.enabled or self.proc is None or self.proc.stdin is None:
            return
        if self.proc.poll() is not None:
            self.enabled = False
            log("overlay process exited")
            return
        try:
            self.proc.stdin.write(json.dumps(event) + "\n")
            self.proc.stdin.flush()
        except Exception as exc:
            self.enabled = False
            log(f"overlay write failed: {exc!r}")


class TrayIndicator:
    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = os.environ.get("BYNUM_DICTATE_TRAY", "1") != "0" if enabled is None else enabled
        self.proc: subprocess.Popen | None = None
        self.stderr = None
        if self.enabled:
            try:
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                self.stderr = (STATE_DIR / "tray.stderr").open("a", encoding="utf-8")
                self.proc = subprocess.Popen(
                    [TRAY_PYTHON, str(APP_DIR / "bynum_dictate_tray.py")],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=self.stderr,
                    text=True,
                    bufsize=1,
                )
                self.status("Loading")
                log("tray indicator process started")
            except Exception as exc:
                self.enabled = False
                log(f"tray indicator disabled: {exc!r}")

    def status(self, status: str) -> None:
        self._send({"status": status})

    def _send(self, event: dict) -> None:
        if not self.enabled or self.proc is None or self.proc.stdin is None:
            return
        if self.proc.poll() is not None:
            self.enabled = False
            log("tray indicator process exited")
            return
        try:
            self.proc.stdin.write(json.dumps(event) + "\n")
            self.proc.stdin.flush()
        except Exception as exc:
            self.enabled = False
            log(f"tray indicator write failed: {exc!r}")


def tone(kind: str, *, wait: bool = False) -> None:
    if os.environ.get("BYNUM_DICTATE_SOUND", "1") == "0":
        return
    player = shutil.which("paplay") or shutil.which("pw-play") or shutil.which("aplay")
    if not player:
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{kind}-bell-v4.wav"
    if not path.exists():
        frequency = {"start": 660, "stop": 523.25, "done": 784, "error": 330}.get(kind, 660)
        duration = {"start": 0.14, "stop": 0.26, "done": 0.34, "error": 0.24}.get(kind, 0.28)
        frames = int(TONE_RATE * duration)
        attack = 0.004 if kind == "start" else 0.006
        decay = {"start": 0.040, "stop": 0.075, "done": 0.095, "error": 0.070}.get(kind, 0.080)
        amplitude = 0.11 if kind != "error" else 0.08
        values = []
        for i in range(frames):
            t = i / TONE_RATE
            env = min(1.0, t / attack) * math.exp(-t / decay)
            wave_value = math.sin(2 * math.pi * frequency * t)
            values.append(int(32767 * amplitude * env * wave_value))
        samples = array.array("h", values)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(TONE_RATE)
            handle.writeframes(samples.tobytes())

    def play() -> None:
        subprocess.run([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    if wait:
        play()
    else:
        threading.Thread(target=play, name=f"bynum-dictate-tone-{kind}", daemon=True).start()


class Recording:
    def __init__(
        self,
        path: pathlib.Path,
        tmp: tempfile.TemporaryDirectory,
        duration: float,
        max_rms: float,
        max_peak: float,
        voice_frames: int,
        speech_frames: int,
    ):
        self.path = path
        self.tmp = tmp
        self.duration = duration
        self.max_rms = max_rms
        self.max_peak = max_peak
        self.voice_frames = voice_frames
        self.speech_frames = speech_frames

    def cleanup(self) -> None:
        self.tmp.cleanup()


class AudioRecorder:
    def __init__(self, overlay: Overlay) -> None:
        self.overlay = overlay
        self.tmp = tempfile.TemporaryDirectory(prefix="bynum-dictate-hold-")
        self.path = pathlib.Path(self.tmp.name) / "recording.wav"
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.wav: wave.Wave_write | None = None
        self.bytes_written = 0
        self.max_rms = 0.0
        self.max_peak = 0.0
        self.voice_frames = 0
        self.speech_frames = 0
        self.analysis_frames = 0
        self.smoothed_level = 0.0
        self.visual_history = [VISUAL_FLOOR_LEVEL] * VISUAL_BAR_COUNT

    def start(self) -> None:
        if not shutil.which("parec"):
            raise RuntimeError("parec is required but was not found")

        self.wav = wave.open(str(self.path), "wb")  # noqa: SIM115 - the reader thread owns the close.
        self.wav.setnchannels(CHANNELS)
        self.wav.setsampwidth(SAMPLE_WIDTH)
        self.wav.setframerate(SAMPLE_RATE)

        cmd = [
            "parec",
            "--record",
            "--raw",
            "--format=s16le",
            f"--rate={SAMPLE_RATE}",
            f"--channels={CHANNELS}",
            "--latency-msec=20",
            "--process-time-msec=20",
            "--client-name=Bynum Dictate",
            "--stream-name=Dictation",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.thread = threading.Thread(target=self._read_loop, name="bynum-dictate-audio", daemon=True)
        self.thread.start()

    def stop(self) -> Recording:
        self.stop_event.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=0.8)

        if self.thread:
            self.thread.join(timeout=1.5)

        duration = self.bytes_written / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
        return Recording(
            self.path,
            self.tmp,
            duration,
            self.max_rms,
            self.max_peak,
            self.voice_frames,
            self.speech_frames,
        )

    def _read_loop(self) -> None:
        assert self.proc is not None
        assert self.proc.stdout is not None
        assert self.wav is not None

        try:
            while not self.stop_event.is_set():
                data = self.proc.stdout.read(CHUNK_BYTES)
                if not data:
                    break
                self.wav.writeframes(data)
                self.bytes_written += len(data)
                self._update_level(data)
        finally:
            with contextlib.suppress(Exception):
                self.wav.close()

    def _update_level(self, data: bytes) -> None:
        samples = array.array("h")
        samples.frombytes(data)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return

        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768.0
        peak = max(abs(sample) for sample in samples) / 32768.0
        self.max_rms = max(self.max_rms, rms)
        self.max_peak = max(self.max_peak, peak)
        heard = rms >= VOICE_THRESHOLD
        self.analysis_frames += 1
        if heard:
            self.voice_frames += 1
            elapsed_ms = self.analysis_frames * CHUNK_FRAMES * 1000 / SAMPLE_RATE
            if elapsed_ms >= IGNORE_START_MS:
                self.speech_frames += 1

        def shape_level(value: float) -> float:
            if value <= VISUAL_NOISE_FLOOR:
                return VISUAL_FLOOR_LEVEL
            db = 20.0 * math.log10(max(value, 0.000001))
            ratio = (db - VISUAL_DB_FLOOR) / max(1.0, VISUAL_DB_CEILING - VISUAL_DB_FLOOR)
            ratio = max(0.0, min(1.0, ratio))
            if ratio <= 0.01:
                return VISUAL_FLOOR_LEVEL
            return min(VISUAL_CEILING, VISUAL_FLOOR_LEVEL + (VISUAL_CEILING - VISUAL_FLOOR_LEVEL) * (ratio**1.32))

        instant = shape_level(rms)
        if instant > self.smoothed_level:
            self.smoothed_level = self.smoothed_level * 0.34 + instant * 0.66
        else:
            self.smoothed_level = self.smoothed_level * 0.76 + instant * 0.24
        self.visual_history = (self.visual_history + [instant])[-VISUAL_BAR_COUNT:]

        window = max(1, len(samples) // VISUAL_BAR_COUNT)
        chunk_levels = []
        for index in range(VISUAL_BAR_COUNT):
            end = len(samples) if index == VISUAL_BAR_COUNT - 1 else (index + 1) * window
            chunk = samples[index * window : end]
            if not chunk:
                chunk_levels.append(self.smoothed_level)
                continue
            chunk_rms = math.sqrt(sum(sample * sample for sample in chunk) / len(chunk)) / 32768.0
            chunk_levels.append(shape_level(chunk_rms))

        average = sum(chunk_levels) / len(chunk_levels)
        bars = []
        for index, shaped in enumerate(chunk_levels):
            contrast = shaped + (shaped - average) * 1.35
            mixed = contrast * 0.86 + self.visual_history[index] * 0.14
            bars.append(max(VISUAL_FLOOR_LEVEL, min(VISUAL_CEILING, mixed)))

        self.overlay.level(self.smoothed_level, heard, bars)


def clamp_sample(value: float) -> int:
    return max(-32768, min(32767, int(round(value))))


def prepared_audio_path(recording: Recording) -> pathlib.Path:
    if not AUDIO_PREP:
        return recording.path

    prepared = recording.path.with_name("prepared.wav")
    try:
        with wave.open(str(recording.path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.readframes(source.getnframes())
    except Exception as exc:
        log(f"audio prep skipped: {exc!r}")
        return recording.path

    if channels != CHANNELS or sample_width != SAMPLE_WIDTH or rate != SAMPLE_RATE:
        log(f"audio prep skipped: unexpected format {channels}ch/{sample_width * 8}bit/{rate}Hz")
        return recording.path

    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return recording.path

    peak = max(abs(sample) for sample in samples)
    gain = 1.0
    normalized_peak = peak / 32768.0
    if peak and normalized_peak >= AUDIO_NORMALIZE_MIN_PEAK:
        target_peak = max(1, int(32767 * AUDIO_NORMALIZE_PEAK))
        gain = min(AUDIO_MAX_GAIN, target_peak / peak)
        if 0.97 <= gain <= 1.03:
            gain = 1.0

    if gain != 1.0:
        samples = array.array("h", (clamp_sample(sample * gain) for sample in samples))

    lead_frames = max(0, int(SAMPLE_RATE * AUDIO_LEAD_IN_MS / 1000))
    tail_frames = max(0, int(SAMPLE_RATE * AUDIO_TAIL_PAD_MS / 1000))
    output = array.array("h", [0]) * lead_frames
    output.extend(samples)
    output.extend(array.array("h", [0]) * tail_frames)

    if sys.byteorder != "little":
        output.byteswap()

    try:
        with wave.open(str(prepared), "wb") as target:
            target.setnchannels(CHANNELS)
            target.setsampwidth(SAMPLE_WIDTH)
            target.setframerate(SAMPLE_RATE)
            target.writeframes(output.tobytes())
        log(
            "prepared audio: "
            f"lead={AUDIO_LEAD_IN_MS}ms, tail={AUDIO_TAIL_PAD_MS}ms, "
            f"peak={normalized_peak:.4f}, gain={gain:.2f}"
        )
        return prepared
    except Exception as exc:
        log(f"audio prep failed: {exc!r}")
        return recording.path


class ModelManager:
    def __init__(self, overlay: Overlay, tray: TrayIndicator) -> None:
        self.overlay = overlay
        self.tray = tray
        self.model: WhisperModel | None = None
        self.error: Exception | None = None
        self.loading = False
        self.condition = threading.Condition()
        if os.environ.get("BYNUM_DICTATE_PRELOAD", "1") != "0":
            threading.Thread(target=self.get, name="bynum-dictate-model-loader", daemon=True).start()

    def get(self) -> WhisperModel:
        with self.condition:
            if self.model is not None:
                return self.model
            if self.error is not None:
                raise self.error
            if self.loading:
                while self.loading and self.error is None and self.model is None:
                    self.condition.wait()
                if self.model is not None:
                    return self.model
                raise self.error or RuntimeError("model failed to load")
            self.loading = True

        try:
            MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            log(f"loading model {MODEL_NAME} on {DEVICE}/{COMPUTE_TYPE}")
            self.tray.status("Loading")
            model = WhisperModel(
                MODEL_NAME,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                download_root=str(MODEL_CACHE),
                local_files_only=LOCAL_FILES_ONLY,
                cpu_threads=1,
                num_workers=1,
            )
            log(f"model ready: {MODEL_NAME}")
            self.tray.status("Ready")
        except Exception as exc:
            self.tray.status("Error")
            with self.condition:
                self.error = exc
                self.loading = False
                self.condition.notify_all()
            raise

        with self.condition:
            self.model = model
            self.loading = False
            self.condition.notify_all()
            return model


def transcribe(recording: Recording, model_manager: ModelManager) -> str:
    model = model_manager.get()
    audio_path = prepared_audio_path(recording)
    hotwords, vocabulary_count = load_vocabulary(
        VOCABULARY_PATH,
        max_chars=VOCABULARY_MAX_CHARS,
        logger=log,
    )
    initial_prompt = None
    if hotwords:
        initial_prompt = f"Prefer these local custom vocabulary terms when they fit the audio: {hotwords}."
        log(f"using custom vocabulary terms: {vocabulary_count}")
    segments, _ = model.transcribe(
        str(audio_path),
        beam_size=BEAM_SIZE,
        language=LANGUAGE,
        vad_filter=VAD_FILTER,
        condition_on_previous_text=False,
        temperature=0.0,
        no_speech_threshold=NO_SPEECH_THRESHOLD,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


class HoldToDictate:
    def __init__(
        self,
        overlay: Overlay,
        tray: TrayIndicator,
        model_manager: ModelManager,
        all_hotkey_keys_up: threading.Event,
    ) -> None:
        self.overlay = overlay
        self.tray = tray
        self.model_manager = model_manager
        self.all_hotkey_keys_up = all_hotkey_keys_up
        self.lock = threading.Lock()
        self.recorder: AudioRecorder | None = None
        self.busy = False
        self.busy_since = 0.0
        self.phase = "idle"
        self.focus_id: int | None = None

    def start(self) -> None:
        with self.lock:
            if self.recorder is not None or self.busy:
                busy_for = time.monotonic() - self.busy_since if self.busy_since else 0.0
                log(f"start ignored: busy phase={self.phase}, busy_for={busy_for:.2f}s")
                self.overlay.show("Busy", "finishing previous dictation")
                if busy_for >= BUSY_STUCK_SECONDS:
                    self.tray.status("Busy")
                    self.overlay.hide(BUSY_STUCK_NOTICE_MS)
                else:
                    self.overlay.hide(BUSY_NOTICE_MS)
                return

            self.focus_id = active_window_id(log)
            self.recorder = AudioRecorder(self.overlay)
            self.busy = True
            self.busy_since = time.monotonic()
            self.phase = "starting"

        try:
            self.tray.status("Listening")
            self.overlay.show("Listening", "hold left Ctrl + left Windows")
            if START_TONE_BEFORE_RECORD:
                tone("start", wait=True)
            self.recorder.start()
            with self.lock:
                self.phase = "listening"
            if not START_TONE_BEFORE_RECORD:
                tone("start")
            log("recording started")
        except Exception as exc:
            log(f"recording failed to start: {exc!r}")
            with self.lock:
                self.recorder = None
                self.busy = False
                self.busy_since = 0.0
                self.phase = "idle"
            self.tray.status("Error")
            self.overlay.show("Error", "could not start microphone")
            self.overlay.hide(1800)

    def stop(self) -> None:
        with self.lock:
            recorder = self.recorder
            self.recorder = None
            focus_id = self.focus_id
            self.focus_id = None

        if recorder is None:
            with self.lock:
                if self.busy:
                    log(f"stop ignored: no active recorder, phase={self.phase}")
            return

        threading.Thread(target=self._finish, args=(recorder, focus_id), name="bynum-dictate-finish", daemon=True).start()

    def _finish(self, recorder: AudioRecorder, focus_id: int | None) -> None:
        recording: Recording | None = None
        try:
            with self.lock:
                self.phase = "finishing"
            self.tray.status("Finishing")
            self.overlay.status("Finishing", "stopping microphone")
            recording = recorder.stop()
            tone("stop")
            log(
                "recording stopped: "
                f"{recording.duration:.2f}s, max_rms={recording.max_rms:.4f}, "
                f"peak={recording.max_peak:.4f}, voice_frames={recording.voice_frames}, "
                f"speech_frames={recording.speech_frames}"
            )

            if recording.duration < 0.18:
                self.tray.status("Ready")
                self.overlay.status("Too Short", "hold a little longer")
                log("recording ignored: too short")
                self.overlay.hide(1100)
                return

            speech_ms = recording.speech_frames * CHUNK_FRAMES * 1000 / SAMPLE_RATE
            if speech_ms < MIN_SPEECH_MS:
                self.tray.status("Ready")
                self.overlay.status("No Speech", "nothing to paste")
                log(f"recording ignored: speech below threshold ({speech_ms:.0f}ms < {MIN_SPEECH_MS}ms)")
                self.overlay.hide(900)
                return

            self.tray.status("Transcribing")
            self.overlay.status("Transcribing", "local GPU")
            with self.lock:
                self.phase = "transcribing"
            started = time.monotonic()
            text = transcribe(recording, self.model_manager)
            elapsed = time.monotonic() - started
            log(f"transcription finished in {elapsed:.2f}s; text_len={len(text)}")
            if not text:
                self.tray.status("Ready")
                self.overlay.status("No Speech", "nothing to paste")
                log("no speech detected by model")
                self.overlay.hide(1200)
                return

            self.tray.status("Pasting")
            self.overlay.status("Pasting", text[:34] + ("..." if len(text) > 34 else ""))
            with self.lock:
                self.phase = "copying"
            copied = copy_to_clipboard(text, log)
            self.all_hotkey_keys_up.wait(timeout=2.5)
            time.sleep(0.08)
            with self.lock:
                self.phase = "pasting"
            pasted = copied and paste_x11(focus_id, logger=log)

            if pasted:
                self.overlay.status("Pasted", "")
                tone("done")
                log(f"pasted transcript: {text!r}")
            elif copied:
                self.overlay.status("Copied", "paste manually with Ctrl+V")
                tone("done")
                log(f"copied transcript; paste unavailable: {text!r}")
            else:
                self.overlay.status("Clipboard Error", "transcript not copied")
                tone("error")
                log(f"clipboard unavailable for transcript: {text!r}")
            self.overlay.hide(1000)
            self.tray.status("Ready")
        except Exception as exc:
            log(f"dictation failed: {exc!r}")
            self.tray.status("Error")
            self.overlay.status("Error", "dictation failed")
            tone("error")
            self.overlay.hide(1800)
        finally:
            if recording is not None:
                recording.cleanup()
            else:
                recorder.tmp.cleanup()
            with self.lock:
                self.busy = False
                self.busy_since = 0.0
                self.phase = "idle"


def main() -> None:
    lock = single_instance()

    overlay = Overlay()
    tray = TrayIndicator()
    model_manager = ModelManager(overlay, tray)
    all_hotkey_keys_up = threading.Event()
    all_hotkey_keys_up.set()
    app = HoldToDictate(overlay, tray, model_manager, all_hotkey_keys_up)

    control_display = display.Display()
    record_display = display.Display()
    if not record_display.has_extension("RECORD"):
        raise SystemExit("X RECORD extension is unavailable")

    left_control = control_display.keysym_to_keycode(XK.string_to_keysym("Control_L"))
    left_super = control_display.keysym_to_keycode(XK.string_to_keysym("Super_L"))
    if not left_control or not left_super:
        raise SystemExit("Could not resolve Control_L/Super_L keycodes")

    state_lock = threading.Lock()
    chord_active = False
    active_since = 0.0
    gesture_consumed = False
    cooldown_until = 0.0
    last_seen_down = {"left_control": 0.0, "left_super": 0.0}
    wake_state = threading.Event()
    stop_poller = threading.Event()

    def key_is_down(keymap: list[int], keycode: int) -> bool:
        return bool(keymap[keycode // 8] & (1 << (keycode % 8)))

    def apply_physical_state(ctrl_down: bool, super_down: bool, reason: str) -> None:
        nonlocal chord_active, active_since, cooldown_until, gesture_consumed
        should_start = False
        should_stop = False
        now = time.monotonic()

        with state_lock:
            if ctrl_down:
                last_seen_down["left_control"] = now
            if super_down:
                last_seen_down["left_super"] = now

            any_down = ctrl_down or super_down
            if any_down:
                all_hotkey_keys_up.clear()
            else:
                all_hotkey_keys_up.set()
                gesture_consumed = False

            recently_chorded = (
                any_down
                and now - last_seen_down["left_control"] <= CHORD_GRACE_SECONDS
                and now - last_seen_down["left_super"] <= CHORD_GRACE_SECONDS
            )

            if recently_chorded and not chord_active and not gesture_consumed and now >= cooldown_until:
                chord_active = True
                active_since = now
                gesture_consumed = True
                should_start = True
            elif chord_active and not any_down:
                chord_active = False
                active_since = 0.0
                cooldown_until = now + RETRIGGER_COOLDOWN_SECONDS
                should_stop = True
            elif chord_active and MAX_RECORD_SECONDS > 0 and now - active_since >= MAX_RECORD_SECONDS:
                chord_active = False
                active_since = 0.0
                cooldown_until = now + RETRIGGER_COOLDOWN_SECONDS
                all_hotkey_keys_up.set()
                should_stop = True
                log(f"recording auto-stopped after {MAX_RECORD_SECONDS:g}s limit")

        if should_start:
            log(f"hotkey state -> recording ({reason})")
            app.start()
        elif should_stop:
            log(f"hotkey state -> finishing ({reason})")
            app.stop()

    def poll_physical_keys() -> None:
        poll_display = display.Display()
        try:
            while not stop_poller.is_set():
                keymap = poll_display.query_keymap()
                apply_physical_state(
                    key_is_down(keymap, left_control),
                    key_is_down(keymap, left_super),
                    "poll",
                )
                wake_state.wait(KEY_POLL_INTERVAL_SECONDS)
                wake_state.clear()
        finally:
            poll_display.close()

    threading.Thread(target=poll_physical_keys, name="bynum-dictate-key-poller", daemon=True).start()

    def handle_event(event) -> None:
        if event.type not in (X.KeyPress, X.KeyRelease) or event.detail not in (left_control, left_super):
            return
        wake_state.set()

    def callback(reply) -> None:
        if reply.category != record.FromServer or reply.client_swapped or not reply.data:
            return

        data = reply.data
        while data:
            event, data = rq.EventField(None).parse_binary_value(data, record_display.display, None, None)
            handle_event(event)

    context = record_display.record_create_context(
        0,
        [record.AllClients],
        [
            {
                "core_requests": (0, 0),
                "core_replies": (0, 0),
                "ext_requests": (0, 0, 0, 0),
                "ext_replies": (0, 0, 0, 0),
                "delivered_events": (0, 0),
                "device_events": (X.KeyPress, X.KeyRelease),
                "errors": (0, 0),
                "client_started": False,
                "client_died": False,
            }
        ],
    )

    log(f"started hold-to-dictate; hotkey is left Control + left Super ({left_control}+{left_super})")
    _ = lock

    try:
        record_display.record_enable_context(context, callback)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log(f"stopped with error: {exc!r}")
        raise
    finally:
        with contextlib.suppress(Exception):
            record_display.record_free_context(context)
        stop_poller.set()
        wake_state.set()
        control_display.close()
        record_display.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"fatal: {exc!r}")
        print(f"bynum-dictate-hotkey: {exc}", file=sys.stderr)
        raise
