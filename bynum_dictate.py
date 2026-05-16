#!/usr/bin/env python3
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import wave

from faster_whisper import WhisperModel

from bynum_dictate_common import (
    DEFAULT_VOCABULARY,
    MODEL_CACHE,
    active_window_id,
    copy_to_clipboard,
    load_vocabulary,
    paste_x11,
)

DEFAULT_MODEL = os.environ.get("BYNUM_DICTATE_MODEL", "tiny.en")
DEFAULT_DEVICE = os.environ.get("BYNUM_DICTATE_DEVICE", "cpu")
DEFAULT_COMPUTE = os.environ.get("BYNUM_DICTATE_COMPUTE", "int8")
DEFAULT_CPU_FALLBACK = os.environ.get("BYNUM_DICTATE_CPU_FALLBACK", "1").lower() not in {"0", "false", "no", "off"}
DEFAULT_CPU_MODEL = os.environ.get("BYNUM_DICTATE_CPU_MODEL", "tiny.en")
DEFAULT_CPU_COMPUTE = os.environ.get("BYNUM_DICTATE_CPU_COMPUTE", "int8")
DEFAULT_BEAM_SIZE = int(os.environ.get("BYNUM_DICTATE_BEAM_SIZE", "1"))
DEFAULT_VAD = os.environ.get("BYNUM_DICTATE_VAD", "0").lower() not in {"0", "false", "no", "off"}
DEFAULT_LOCAL_ONLY = os.environ.get("BYNUM_DICTATE_LOCAL_ONLY", "1") != "0"
DEFAULT_NO_SPEECH_THRESHOLD = float(os.environ.get("BYNUM_DICTATE_NO_SPEECH_THRESHOLD", "0.45"))
VOCABULARY_MAX_CHARS = int(os.environ.get("BYNUM_DICTATE_VOCABULARY_MAX_CHARS", "1800"))
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1
CHUNK_FRAMES = 800
CHUNK_BYTES = CHUNK_FRAMES * SAMPLE_WIDTH * CHANNELS


def die(message: str, code: int = 1) -> None:
    print(f"bynum-dictate: {message}", file=sys.stderr)
    raise SystemExit(code)


def log_stderr(message: str) -> None:
    print(f"[{message}]", file=sys.stderr)


def is_cuda_unavailable_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "cuda failed",
            "cuda-capable device",
            "cuda driver",
            "cuda runtime",
            "cublas",
            "cudnn",
            "no kernel image",
        )
    )


def can_fallback_to_cpu(args: argparse.Namespace, exc: BaseException) -> bool:
    return args.cpu_fallback and args.device != "cpu" and is_cuda_unavailable_error(exc)


def load_model(args: argparse.Namespace, *, device: str | None = None, compute_type: str | None = None) -> WhisperModel:
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    return WhisperModel(
        args.model,
        device=device or args.device,
        compute_type=compute_type or args.compute_type,
        download_root=str(MODEL_CACHE),
        local_files_only=args.local_only,
        cpu_threads=1,
        num_workers=1,
    )


def load_model_with_fallback(args: argparse.Namespace) -> WhisperModel:
    try:
        return load_model(args)
    except Exception as exc:
        if not can_fallback_to_cpu(args, exc):
            raise
        log_stderr(f"CUDA unavailable; falling back to {args.cpu_model} on cpu/{args.cpu_compute_type}: {exc!r}")
        args.model = args.cpu_model
        args.device = "cpu"
        args.compute_type = args.cpu_compute_type
        return load_model(args)


def transcribe_with_model(model: WhisperModel, path: pathlib.Path, args: argparse.Namespace, initial_prompt: str | None, hotwords: str | None):
    return model.transcribe(
        str(path),
        beam_size=args.beam_size,
        language=args.language,
        vad_filter=not args.no_vad,
        condition_on_previous_text=False,
        temperature=0.0,
        no_speech_threshold=args.no_speech_threshold,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
    )


def transcribe_audio(path: pathlib.Path, args: argparse.Namespace) -> str:
    if not path.exists():
        die(f"audio file not found: {path}")

    model = load_model_with_fallback(args)
    hotwords, vocabulary_count = load_vocabulary(
        pathlib.Path(args.vocabulary),
        max_chars=VOCABULARY_MAX_CHARS,
        logger=log_stderr,
    )
    initial_prompt = None
    if hotwords:
        initial_prompt = f"Prefer these local custom vocabulary terms when they fit the audio: {hotwords}."
        if args.verbose:
            print(f"[custom vocabulary terms: {vocabulary_count}]", file=sys.stderr)
    try:
        segments, info = transcribe_with_model(model, path, args, initial_prompt, hotwords)
    except Exception as exc:
        if not can_fallback_to_cpu(args, exc):
            raise
        log_stderr(f"CUDA unavailable; falling back to {args.cpu_model} on cpu/{args.cpu_compute_type}: {exc!r}")
        args.model = args.cpu_model
        args.device = "cpu"
        args.compute_type = args.cpu_compute_type
        model = load_model(args)
        segments, info = transcribe_with_model(model, path, args, initial_prompt, hotwords)
    text = " ".join(segment.text.strip() for segment in segments).strip()

    if args.verbose:
        lang = getattr(info, "language", None)
        prob = getattr(info, "language_probability", None)
        if lang:
            suffix = f" ({prob:.2f})" if isinstance(prob, float) else ""
            print(f"[language: {lang}{suffix}]", file=sys.stderr)

    return text


def record_audio(seconds: float, target: pathlib.Path) -> None:
    if not shutil.which("parec"):
        die("parec is required but was not found")

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

    print(f"Recording {seconds:g}s...", file=sys.stderr)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    bytes_written = 0
    deadline = time.monotonic() + max(0.0, seconds)
    try:
        if proc.stdout is None:
            die("recording failed: parec stdout pipe was not opened")
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(SAMPLE_WIDTH)
            wav.setframerate(SAMPLE_RATE)
            while time.monotonic() < deadline:
                data = proc.stdout.read(CHUNK_BYTES)
                if not data:
                    break
                wav.writeframes(data)
                bytes_written += len(data)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=0.8)
    stderr = b""
    if proc.stderr is not None:
        stderr = proc.stderr.read()

    if proc.returncode not in (0, -15, -2):
        detail = stderr.decode("utf-8", "ignore").strip()
        die(f"recording failed{': ' + detail if detail else ''}")

    if not target.exists() or bytes_written == 0:
        die("recording produced no audio")



def notify(title: str, message: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def handle_text(text: str, args: argparse.Namespace) -> None:
    print(text)

    copied = False
    if args.copy or args.paste:
        copied = copy_to_clipboard(text, log_stderr)
        if copied and args.verbose:
            print("[copied to clipboard]", file=sys.stderr)
        elif args.copy or args.paste:
            print("[clipboard copy unavailable]", file=sys.stderr)

    if args.paste and copied:
        time.sleep(args.paste_delay)
        target_window = active_window_id(log_stderr)
        if not paste_x11(target_window, logger=log_stderr) and args.verbose:
            print("[paste unavailable; transcript remains on clipboard]", file=sys.stderr)


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model alias or path (default: {DEFAULT_MODEL})")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["cuda", "cpu", "auto"], help=f"inference device (default: {DEFAULT_DEVICE})")
    parser.add_argument("--compute-type", default=DEFAULT_COMPUTE, help=f"CTranslate2 compute type (default: {DEFAULT_COMPUTE})")
    parser.add_argument("--cpu-fallback", dest="cpu_fallback", action="store_true", default=DEFAULT_CPU_FALLBACK, help="fall back to CPU if CUDA is unavailable")
    parser.add_argument("--no-cpu-fallback", dest="cpu_fallback", action="store_false", help="do not fall back to CPU if CUDA is unavailable")
    parser.add_argument("--cpu-model", default=DEFAULT_CPU_MODEL, help=f"model to use for CPU fallback (default: {DEFAULT_CPU_MODEL})")
    parser.add_argument("--cpu-compute-type", default=DEFAULT_CPU_COMPUTE, help=f"CTranslate2 compute type for CPU fallback (default: {DEFAULT_CPU_COMPUTE})")
    parser.add_argument("--language", default="en", help="language hint, or empty string to auto-detect")
    parser.add_argument("--beam-size", type=int, default=DEFAULT_BEAM_SIZE, help="beam size; higher is more accurate but slower")
    parser.add_argument("--vad", dest="no_vad", action="store_false", help="enable voice activity filtering")
    parser.add_argument("--no-vad", dest="no_vad", action="store_true", default=not DEFAULT_VAD, help="disable voice activity filtering")
    parser.add_argument("--no-speech-threshold", type=float, default=DEFAULT_NO_SPEECH_THRESHOLD, help="Whisper no-speech threshold")
    parser.add_argument("--vocabulary", default=str(DEFAULT_VOCABULARY), help="custom vocabulary file, one term per line")
    parser.add_argument("--local-only", dest="local_only", action="store_true", default=DEFAULT_LOCAL_ONLY, help="use only locally cached models")
    parser.add_argument("--allow-download", dest="local_only", action="store_false", help="allow model downloads if missing")
    parser.add_argument("--verbose", action="store_true", help="print extra status")


def add_output_args(parser: argparse.ArgumentParser, copy_default: bool) -> None:
    parser.add_argument("--copy", dest="copy", action="store_true", default=copy_default, help="copy transcript to clipboard")
    parser.add_argument("--no-copy", dest="copy", action="store_false", help="do not copy transcript to clipboard")
    parser.add_argument("--paste", action="store_true", help="paste into the active X11 window after copying")
    parser.add_argument("--paste-delay", type=float, default=0.15, help="seconds to wait before paste")
    parser.add_argument("--notify", action="store_true", help="show desktop notifications")


def cmd_file(args: argparse.Namespace) -> None:
    if args.language == "":
        args.language = None
    text = transcribe_audio(pathlib.Path(args.audio_file).expanduser(), args)
    handle_text(text, args)


def cmd_record(args: argparse.Namespace) -> None:
    if args.language == "":
        args.language = None
    with tempfile.TemporaryDirectory(prefix="bynum-dictate-") as tmp:
        audio_path = pathlib.Path(tmp) / "recording.wav"
        if args.notify:
            notify("Bynum Dictate", f"Recording {args.seconds:g} seconds")
        record_audio(args.seconds, audio_path)
        text = transcribe_audio(audio_path, args)
    handle_text(text, args)
    if args.notify:
        notify("Bynum Dictate", "Transcript ready" if text else "No speech detected")


def cmd_warmup(args: argparse.Namespace) -> None:
    load_model_with_fallback(args)
    print(f"Model ready: {args.model} on {args.device}/{args.compute_type}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local speech-to-text transcription helper")
    sub = parser.add_subparsers(dest="command")

    record = sub.add_parser("record", help="record the microphone and transcribe it")
    add_common_model_args(record)
    add_output_args(record, copy_default=True)
    record.add_argument("--seconds", type=float, default=float(os.environ.get("BYNUM_DICTATE_SECONDS", "8")))
    record.set_defaults(func=cmd_record)

    file_cmd = sub.add_parser("file", help="transcribe an audio/video file")
    add_common_model_args(file_cmd)
    add_output_args(file_cmd, copy_default=False)
    file_cmd.add_argument("audio_file")
    file_cmd.set_defaults(func=cmd_file)

    warmup = sub.add_parser("warmup", help="download/load the selected model")
    add_common_model_args(warmup)
    warmup.set_defaults(func=cmd_warmup)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(["record"])
    args.func(args)


if __name__ == "__main__":
    main()
