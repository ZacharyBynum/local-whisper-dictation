# Changelog

## Unreleased

- Updated documentation for the lightweight CPU defaults, optional CUDA profile, CPU fallback behavior, sticky recording, and current environment variables.
- Updated stale user-facing references to the old project-name and CUDA-only wording.
- Made CUDA wheel installation opt-in for standalone installs and aligned `warmup` with transcription CPU fallback behavior.
- Updated package license metadata to current SPDX-style fields for clean modern builds.
- Added a source distribution manifest so release archives include install scripts, requirements, and project docs.
- Moved the hotkey lock file into the app state directory and replaced production asserts with runtime checks.

## 0.1.0 - 2026-05-10

- Added hold-to-dictate hotkey daemon for left Control + left Windows.
- Added bottom-center overlay with live waveform and state feedback.
- Added Cinnamon/Gtk tray indicator.
- Added local-only `faster-whisper` transcription defaults.
- Added custom vocabulary hotwords file.
- Added terminal-aware paste behavior.
- Added nonblocking clipboard ownership handling.
- Added restart helper and overlay restart control for stuck states.
- Added installer, autostart template, package metadata, tests, and CI scaffolding.
- Added first-class `bynum-dictate-once` and `bynum-dictate-restart` package entry points.
- Added Dependabot, pull request template, EditorConfig, and Makefile quality gates.
