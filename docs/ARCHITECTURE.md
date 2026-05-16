# Architecture

Bynum Dictate is a small desktop daemon and helper CLI for local X11 dictation.

## Runtime Flow

1. `bynum_dictate_hotkey.py` listens for the X11 left Control + left Windows chord.
2. While the keys are held, `AudioRecorder` captures microphone audio from `parec` into a temporary 16 kHz mono WAV file.
3. On release, the daemon gates out very short/no-speech captures, prepares the WAV, and transcribes it with the configured `faster-whisper` model.
4. The transcript is copied to the local clipboard and pasted into the original active X11 window.
5. The overlay and tray receive JSON status messages from the daemon over stdin.

Pressing Space while the hotkey chord is active latches recording for hands-free dictation. Pressing Space again, or pressing the chord again, stops the latched recording.

## Components

- `bynum_dictate_hotkey.py`: long-running hotkey daemon, audio capture, model lifecycle, transcription, paste orchestration.
- `bynum_dictate_common.py`: shared paths, vocabulary loading, clipboard, active-window detection, terminal detection, and X11 paste helpers.
- `bynum_dictate_overlay.py`: minimal Tk/XShape bottom-center pill with waveform, state text, and restart affordance.
- `bynum_dictate_tray.py`: Gtk tray indicator and quick links to logs/vocabulary.
- `bynum_dictate.py`: command-line transcription and fixed-duration recording helper.
- `bynum_dictate_once.py`: thin wrapper for one fixed-duration record, paste, and notify cycle.
- `bynum_dictate_restart.py`: helper that finds and restarts the background hotkey process.
- `bynum_dictate_text_render.py`: Pillow text renderer used by the overlay for smoother status text.

## Local-Only Model

The hotkey daemon defaults to `BYNUM_DICTATE_LOCAL_ONLY=1`. It loads models from `~/.local/share/bynum-dictate/models` and does not download during normal dictation. Users explicitly opt into a download with:

```bash
bynum-dictate warmup --allow-download
```

The current default profile is `tiny.en` on CPU with `int8` compute. Larger CUDA-backed profiles are opt-in with environment variables such as:

```bash
BYNUM_DICTATE_MODEL=distil-large-v3.5 BYNUM_DICTATE_DEVICE=cuda BYNUM_DICTATE_COMPUTE=float16 bynum-dictate-hotkey
```

If CUDA is requested and unavailable, the daemon falls back to `BYNUM_DICTATE_CPU_MODEL` on CPU unless `BYNUM_DICTATE_CPU_FALLBACK=0` is set.

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
