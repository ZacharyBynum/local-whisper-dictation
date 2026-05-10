# Contributing

Thanks for improving Bynum Dictate. The project goal is a small, reliable Linux dictation tool that stays local by default.

## Development Setup

```bash
git clone https://github.com/ZacharyBynum/bynum-dictate.git
cd bynum-dictate
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For NVIDIA GPU use, install CUDA Python wheels too:

```bash
python -m pip install -e ".[cuda,dev]"
```

System packages are still required for desktop integration:

```bash
sudo apt install pulseaudio-utils xclip wl-clipboard x11-xserver-utils python3-gi gir1.2-gtk-3.0 python3-pil
```

## Quality Gates

Run these before opening a pull request:

```bash
make check
```

## Design Principles

- Audio and transcripts stay local by default.
- UI feedback must match the real state of the daemon.
- The hotkey path should remain fast and lightweight.
- X11 and clipboard operations must fail safely and recover cleanly.
- Avoid adding background services, cloud calls, or telemetry without explicit user opt-in.

## Pull Requests

Include:

- What changed and why.
- How it was tested.
- Any distro, desktop environment, GPU, or audio stack assumptions.
- Screenshots or recordings for overlay changes.
