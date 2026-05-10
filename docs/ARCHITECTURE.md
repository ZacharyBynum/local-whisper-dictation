# Architecture

Local Whisper Dictation is a small desktop daemon made of five cooperating pieces.

## Runtime Flow

1. `local_whisper_hotkey.py` listens for the X11 left Control + left Windows chord.
2. While the keys are held, `AudioRecorder` captures microphone audio from `parec` into a temporary 16 kHz mono WAV file.
3. On release, the daemon gates out very short/no-speech captures, prepares the WAV, and transcribes it with `faster-whisper`.
4. The transcript is copied to the local clipboard and pasted into the original active X11 window.
5. The overlay and tray receive JSON status messages from the daemon over stdin.

## Components

- `local_whisper_hotkey.py`: long-running hotkey daemon, audio capture, model lifecycle, transcription, paste orchestration.
- `local_whisper_common.py`: shared paths, vocabulary loading, clipboard, active-window detection, terminal detection, and X11 paste helpers.
- `local_whisper_overlay.py`: minimal Tk/XShape bottom-center pill with waveform, state text, and restart affordance.
- `local_whisper_tray.py`: Gtk tray indicator and quick links to logs/vocabulary.
- `local_whisper.py`: command-line transcription and fixed-duration recording helper.
- `local_whisper_text_render.py`: Pillow text renderer used by the overlay for smoother status text.

## Local-Only Model

The hotkey daemon defaults to `LOCAL_WHISPER_LOCAL_ONLY=1`. It loads models from `~/.local/share/local-whisper/models` and does not download during normal dictation. Users explicitly opt into a download with:

```bash
local-whisper warmup --allow-download
```

## State Model

The hotkey daemon tracks a small internal phase:

- `idle`
- `starting`
- `listening`
- `finishing`
- `transcribing`
- `copying`
- `pasting`

Duplicate hotkey presses while a phase is active show a short `Busy` state. If the app has been busy longer than the stuck threshold, the overlay keeps the pill visible long enough to expose the restart control.

## Clipboard and Paste

Clipboard ownership is intentionally nonblocking. `xclip` can remain alive as the clipboard owner; the daemon treats that as success after a short readiness timeout instead of waiting forever.

Terminal windows are detected from X11 window class/name hints. They receive `Ctrl+Shift+V`; other windows receive `Ctrl+V`.

## Privacy Boundary

No transcript or audio leaves the machine during dictation. The only network-facing operation is explicit model download when local-only mode is disabled or `--allow-download` is used.
