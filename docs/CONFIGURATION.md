# Configuration

Local Whisper Dictation is configured with environment variables and one vocabulary file.

## Files

- App directory: `~/.local/share/local-whisper`
- Model cache: `~/.local/share/local-whisper/models`
- Config directory: `~/.config/local-whisper`
- Vocabulary file: `~/.config/local-whisper/vocabulary.txt`
- State/log directory: `~/.local/state/local-whisper`
- Autostart entry: `~/.config/autostart/local-whisper-hotkey.desktop`

## Model Settings

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_WHISPER_MODEL` | `distil-large-v3.5` | Faster-Whisper model alias or local path. |
| `LOCAL_WHISPER_DEVICE` | `cuda` | Inference device: `cuda`, `cpu`, or `auto`. |
| `LOCAL_WHISPER_COMPUTE` | `float16` | CTranslate2 compute type. |
| `LOCAL_WHISPER_BEAM_SIZE` | `3` | Beam size. Higher can improve accuracy at a speed cost. |
| `LOCAL_WHISPER_LANGUAGE` | `en` | Language hint. Empty string enables auto-detect. |
| `LOCAL_WHISPER_LOCAL_ONLY` | `1` | Prevent runtime model downloads. |

## Hotkey Settings

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_WHISPER_CHORD_GRACE` | `0.70` | Seconds allowed between pressing left Control and left Windows. |
| `LOCAL_WHISPER_MAX_SECONDS` | `45` | Maximum recording duration before auto-stop. |
| `LOCAL_WHISPER_RETRIGGER_COOLDOWN` | `0.30` | Delay before another recording can start. |
| `LOCAL_WHISPER_KEY_POLL_INTERVAL` | `0.08` | Physical key polling interval. |

## Audio Settings

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_WHISPER_VOICE_THRESHOLD` | `0.012` | RMS threshold used for speech gating. |
| `LOCAL_WHISPER_IGNORE_START_MS` | `360` | Initial capture window ignored for speech gating. |
| `LOCAL_WHISPER_MIN_SPEECH_MS` | `180` | Minimum detected speech required before transcription. |
| `LOCAL_WHISPER_AUDIO_PREP` | `1` | Enable WAV preparation. |
| `LOCAL_WHISPER_LEAD_IN_MS` | `40` | Silence prepended before transcription. |
| `LOCAL_WHISPER_TAIL_PAD_MS` | `40` | Silence appended before transcription. |
| `LOCAL_WHISPER_NORMALIZE_PEAK` | `0.86` | Target peak when normalization is applied. |
| `LOCAL_WHISPER_NORMALIZE_MIN_PEAK` | `0.025` | Do not boost captures below this peak. |
| `LOCAL_WHISPER_MAX_GAIN` | `2.25` | Maximum normalization gain. |

## UI Settings

| Variable | Default | Description |
| --- | --- | --- |
| `LOCAL_WHISPER_OVERLAY` | `1` | Enable the bottom-center pill overlay. |
| `LOCAL_WHISPER_TRAY` | `1` | Enable the tray indicator. |
| `LOCAL_WHISPER_SOUND` | `1` | Enable start/stop/done/error tones. |
| `LOCAL_WHISPER_OVERLAY_RENDER_MS` | `8` | Overlay render loop interval while visible. |
| `LOCAL_WHISPER_OVERLAY_ANIMATION_MS` | `75` | Pill animation duration. |
| `LOCAL_WHISPER_TEXT_RENDER_PYTHON` | `/usr/bin/python3` | Python used for Pillow text rendering. |

## Vocabulary

Put one term per line in:

```bash
~/.config/local-whisper/vocabulary.txt
```

Blank lines and `#` comments are ignored. Terms are deduplicated case-insensitively and passed to Faster-Whisper as hotwords plus a short initial prompt.
