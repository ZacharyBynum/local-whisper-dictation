# Security Policy

## Supported Versions

Bynum Dictate is pre-1.0. Security fixes target the latest commit on the default branch until formal releases begin.

## Reporting a Vulnerability

Please open a private security advisory on GitHub when the repository is published, or email the maintainer listed on the repository profile.

Do not include secrets, private recordings, transcripts, or microphone captures in public issues.

## Privacy Model

- Dictation audio is recorded locally.
- Transcription runs locally with `faster-whisper`.
- Model downloads happen only when explicitly allowed, such as `bynum-dictate warmup --allow-download` or `BYNUM_DICTATE_LOCAL_ONLY=0`.
- No telemetry, analytics, cloud transcription, or transcript upload is implemented.

## High-Risk Areas

- Clipboard ownership and paste automation.
- X11 active-window inspection and synthetic key events.
- Autostart and restart scripts.
- Model download sources and cache paths.
