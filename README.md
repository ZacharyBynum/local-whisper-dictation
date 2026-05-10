# Local Whisper Dictation

[![CI](https://github.com/ZacharyBynum/local-whisper-dictation/actions/workflows/ci.yml/badge.svg)](https://github.com/ZacharyBynum/local-whisper-dictation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Linux X11](https://img.shields.io/badge/platform-Linux%20X11-success.svg)](docs/ARCHITECTURE.md)

Local hold-to-dictate speech-to-text for Linux/X11 with NVIDIA GPU inference through `faster-whisper`.

The default workflow is similar to Whispr: hold **left Control + left Windows**, speak, release, then the transcript is copied and pasted into the active window. Terminal windows use `Ctrl+Shift+V`; other X11 windows use `Ctrl+V`.

## What Runs Locally

- Audio is recorded from the local microphone with `parec`.
- Transcription runs locally with `faster-whisper` and CTranslate2.
- The default model cache is `~/.local/share/local-whisper/models`.
- `LOCAL_WHISPER_LOCAL_ONLY=1` is the default, so the hotkey daemon will not download a model at runtime. Run `local-whisper warmup --allow-download` once when you intentionally want to fetch the model.
- Custom vocabulary is read from `~/.config/local-whisper/vocabulary.txt`.

## Install

System packages on Linux Mint/Ubuntu:

```bash
sudo apt install python3-venv pulseaudio-utils pipewire-audio-client-libraries xclip wl-clipboard x11-xserver-utils python3-gi gir1.2-gtk-3.0 python3-pil
```

Install or refresh the app:

```bash
git clone https://github.com/ZacharyBynum/local-whisper-dictation.git
cd local-whisper-dictation
./install.sh
```

Download/cache the default model when you choose to allow network access:

```bash
local-whisper warmup --allow-download
```

Start the hotkey daemon:

```bash
local-whisper-hotkey
```

The installer writes `~/.config/autostart/local-whisper-hotkey.desktop`, so the daemon starts on login.

## Project Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Configuration](docs/CONFIGURATION.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Security and privacy](SECURITY.md)

## Commands

```bash
local-whisper warmup --allow-download
local-whisper record --seconds 8
local-whisper-dictate --seconds 8
local-whisper file ~/Downloads/audio.mp3
local-whisper-hotkey
local-whisper-restart
```

## Custom Vocabulary

Edit:

```bash
~/.config/local-whisper/vocabulary.txt
```

Use one term per line:

```text
CTranslate2
faster-whisper
Local Whisper
project-specific phrase
```

The terms are passed to `faster-whisper` as hotwords and as a short initial prompt. This is deterministic prompt biasing, not an LLM correction pass.

## Useful Settings

```bash
LOCAL_WHISPER_MODEL=large-v3-turbo local-whisper-hotkey
LOCAL_WHISPER_OVERLAY=0 local-whisper-hotkey
LOCAL_WHISPER_SOUND=0 local-whisper-hotkey
LOCAL_WHISPER_PRELOAD=0 local-whisper-hotkey
LOCAL_WHISPER_CHORD_GRACE=0.9 local-whisper-hotkey
LOCAL_WHISPER_LOCAL_ONLY=0 local-whisper-hotkey
```

Audio and hallucination controls:

```bash
LOCAL_WHISPER_VOICE_THRESHOLD=0.012
LOCAL_WHISPER_MIN_SPEECH_MS=180
LOCAL_WHISPER_IGNORE_START_MS=360
LOCAL_WHISPER_NORMALIZE_PEAK=0.86
LOCAL_WHISPER_NORMALIZE_MIN_PEAK=0.025
LOCAL_WHISPER_MAX_GAIN=2.25
```

Overlay controls:

```bash
LOCAL_WHISPER_OVERLAY_RENDER_MS=8
LOCAL_WHISPER_OVERLAY_ANIMATION_MS=75
LOCAL_WHISPER_TEXT_RENDER_PYTHON=/usr/bin/python3
```

Defaults:

- Model: `distil-large-v3.5`
- Device: `cuda`
- Compute type: `float16`
- Hotkey: left Control + left Windows
- Model cache: `~/.local/share/local-whisper/models`

## Troubleshooting

Logs live in:

```bash
~/.local/state/local-whisper/
```

Useful checks:

```bash
tail -n 80 ~/.local/state/local-whisper/hotkey.log
tail -n 80 ~/.local/state/local-whisper/overlay.stderr
tail -n 80 ~/.local/state/local-whisper/tray.stderr
ps -ef | grep local_whisper
```

If the overlay is square or uses the wrong font, check `overlay.stderr`. The overlay uses Tk for the window, XShape for rounded clipping, and `/usr/bin/python3` with Pillow for smooth Ubuntu/Noto text rendering.

When the pill shows `Busy`, `Stopping`, `Thinking`, `Pasting`, `Clipboard error`, or `Error`, it displays a small restart control on the right side. Clicking it asks for confirmation, then restarts the background service.
