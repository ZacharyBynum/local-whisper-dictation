# Bynum Dictate

[![CI](https://github.com/ZacharyBynum/bynum-dictate/actions/workflows/ci.yml/badge.svg)](https://github.com/ZacharyBynum/bynum-dictate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Linux X11](https://img.shields.io/badge/platform-Linux%20X11-success.svg)](docs/ARCHITECTURE.md)

Local hold-to-dictate speech-to-text for Linux/X11 with `faster-whisper`. It defaults to a lightweight CPU profile and can be pointed at NVIDIA CUDA for larger models.

The default workflow is similar to Whispr: hold **left Control + left Windows**, speak, release, then the transcript is copied and pasted into the active window. Press **Space** while the chord is active to latch recording, then press **Space** or the chord again to stop. Terminal windows use `Ctrl+Shift+V`; other X11 windows use `Ctrl+V`.

## What Runs Locally

- Audio is recorded from the local microphone with `parec`.
- Transcription runs locally with `faster-whisper` and CTranslate2.
- The default model cache is `~/.local/share/bynum-dictate/models`.
- The default runtime profile is `tiny.en` on CPU with `int8` compute for fast startup and broad compatibility.
- Set `BYNUM_DICTATE_DEVICE=cuda`, `BYNUM_DICTATE_COMPUTE=float16`, and a larger `BYNUM_DICTATE_MODEL` when you want GPU-backed transcription.
- `BYNUM_DICTATE_LOCAL_ONLY=1` is the default, so the hotkey daemon will not download a model at runtime. Run `bynum-dictate warmup --allow-download` once when you intentionally want to fetch the model.
- Custom vocabulary is read from `~/.config/bynum-dictate/vocabulary.txt`.

## Install

System packages on Linux Mint/Ubuntu:

```bash
sudo apt install python3-venv python3-tk pulseaudio-utils pipewire-audio-client-libraries xclip wl-clipboard x11-xserver-utils python3-gi gir1.2-gtk-3.0 python3-pil libnotify-bin
```

Install or refresh the app:

```bash
git clone https://github.com/ZacharyBynum/bynum-dictate.git
cd bynum-dictate
./install.sh
```

To install NVIDIA CUDA runtime wheels for larger GPU-backed models:

```bash
BYNUM_DICTATE_INSTALL_CUDA=1 ./install.sh
```

Download/cache the default model when you choose to allow network access:

```bash
bynum-dictate warmup --allow-download
```

Start the hotkey daemon:

```bash
bynum-dictate-hotkey
```

The installer writes `~/.config/autostart/bynum-dictate-hotkey.desktop`, so the daemon starts on login.

## Project Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Configuration](docs/CONFIGURATION.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Security and privacy](SECURITY.md)

## Commands

```bash
bynum-dictate warmup --allow-download
BYNUM_DICTATE_MODEL=distil-large-v3.5 BYNUM_DICTATE_DEVICE=cuda BYNUM_DICTATE_COMPUTE=float16 bynum-dictate warmup --allow-download
bynum-dictate record --seconds 8
bynum-dictate-once --seconds 8
bynum-dictate file ~/Downloads/audio.mp3
bynum-dictate-hotkey
bynum-dictate-restart
```

## Custom Vocabulary

Edit:

```bash
~/.config/bynum-dictate/vocabulary.txt
```

Use one term per line:

```text
CTranslate2
faster-whisper
Bynum Dictate
project-specific phrase
```

The terms are passed to `faster-whisper` as hotwords and as a short initial prompt. This is deterministic prompt biasing, not an LLM correction pass.

## Useful Settings

```bash
BYNUM_DICTATE_MODEL=distil-large-v3.5 BYNUM_DICTATE_DEVICE=cuda BYNUM_DICTATE_COMPUTE=float16 bynum-dictate-hotkey
BYNUM_DICTATE_MODEL=large-v3-turbo BYNUM_DICTATE_DEVICE=cuda BYNUM_DICTATE_COMPUTE=float16 bynum-dictate-hotkey
BYNUM_DICTATE_OVERLAY=0 bynum-dictate-hotkey
BYNUM_DICTATE_SOUND=0 bynum-dictate-hotkey
BYNUM_DICTATE_PRELOAD=0 bynum-dictate-hotkey
BYNUM_DICTATE_CHORD_GRACE=0.9 bynum-dictate-hotkey
BYNUM_DICTATE_LOCAL_ONLY=0 bynum-dictate-hotkey
BYNUM_DICTATE_CPU_FALLBACK=0 bynum-dictate-hotkey
```

Audio and hallucination controls:

```bash
BYNUM_DICTATE_VAD=1
BYNUM_DICTATE_NO_SPEECH_THRESHOLD=0.45
BYNUM_DICTATE_VOICE_THRESHOLD=0.012
BYNUM_DICTATE_MIN_SPEECH_MS=180
BYNUM_DICTATE_IGNORE_START_MS=360
BYNUM_DICTATE_NORMALIZE_PEAK=0.86
BYNUM_DICTATE_NORMALIZE_MIN_PEAK=0.025
BYNUM_DICTATE_MAX_GAIN=2.25
```

Overlay controls:

```bash
BYNUM_DICTATE_OVERLAY_RENDER_MS=8
BYNUM_DICTATE_OVERLAY_ANIMATION_MS=75
BYNUM_DICTATE_TEXT_RENDER_PYTHON=/usr/bin/python3
BYNUM_DICTATE_READY_NOTIFICATION=0
```

Defaults:

- Model: `tiny.en`
- Device: `cpu`
- Compute type: `int8`
- Beam size: `1`
- CPU fallback: enabled when CUDA is requested and unavailable
- Hotkey: left Control + left Windows
- Model cache: `~/.local/share/bynum-dictate/models`

## Troubleshooting

Logs live in:

```bash
~/.local/state/bynum-dictate/
```

Useful checks:

```bash
tail -n 80 ~/.local/state/bynum-dictate/hotkey.log
tail -n 80 ~/.local/state/bynum-dictate/overlay.stderr
tail -n 80 ~/.local/state/bynum-dictate/tray.stderr
ps -ef | grep bynum_dictate
```

If the overlay is square or uses the wrong font, check `overlay.stderr`. The overlay uses Tk for the window, XShape for rounded clipping, and `/usr/bin/python3` with Pillow for smooth Ubuntu/Noto text rendering.

When the pill shows `Busy`, `Stopping`, `Thinking`, `Pasting`, `Clipboard error`, or `Error`, it displays a small restart control on the right side. Clicking it asks for confirmation, then restarts the background service.
