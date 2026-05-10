# Configuration

Bynum Dictate is configured with environment variables and one vocabulary file.

## Files

- App directory: `~/.local/share/bynum-dictate`
- Model cache: `~/.local/share/bynum-dictate/models`
- Config directory: `~/.config/bynum-dictate`
- Vocabulary file: `~/.config/bynum-dictate/vocabulary.txt`
- State/log directory: `~/.local/state/bynum-dictate`
- Autostart entry: `~/.config/autostart/bynum-dictate-hotkey.desktop`

## Model Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_MODEL` | `distil-large-v3.5` | Faster-Whisper model alias or local path. |
| `BYNUM_DICTATE_DEVICE` | `cuda` | Inference device: `cuda`, `cpu`, or `auto`. |
| `BYNUM_DICTATE_COMPUTE` | `float16` | CTranslate2 compute type. |
| `BYNUM_DICTATE_BEAM_SIZE` | `3` | Beam size. Higher can improve accuracy at a speed cost. |
| `BYNUM_DICTATE_LANGUAGE` | `en` | Language hint. Empty string enables auto-detect. |
| `BYNUM_DICTATE_LOCAL_ONLY` | `1` | Prevent runtime model downloads. |

## Hotkey Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_CHORD_GRACE` | `0.70` | Seconds allowed between pressing left Control and left Windows. |
| `BYNUM_DICTATE_MAX_SECONDS` | `45` | Maximum recording duration before auto-stop. |
| `BYNUM_DICTATE_RETRIGGER_COOLDOWN` | `0.30` | Delay before another recording can start. |
| `BYNUM_DICTATE_KEY_POLL_INTERVAL` | `0.08` | Physical key polling interval. |

## Audio Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_VOICE_THRESHOLD` | `0.012` | RMS threshold used for speech gating. |
| `BYNUM_DICTATE_IGNORE_START_MS` | `360` | Initial capture window ignored for speech gating. |
| `BYNUM_DICTATE_MIN_SPEECH_MS` | `180` | Minimum detected speech required before transcription. |
| `BYNUM_DICTATE_AUDIO_PREP` | `1` | Enable WAV preparation. |
| `BYNUM_DICTATE_LEAD_IN_MS` | `40` | Silence prepended before transcription. |
| `BYNUM_DICTATE_TAIL_PAD_MS` | `40` | Silence appended before transcription. |
| `BYNUM_DICTATE_NORMALIZE_PEAK` | `0.86` | Target peak when normalization is applied. |
| `BYNUM_DICTATE_NORMALIZE_MIN_PEAK` | `0.025` | Do not boost captures below this peak. |
| `BYNUM_DICTATE_MAX_GAIN` | `2.25` | Maximum normalization gain. |

## UI Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_OVERLAY` | `1` | Enable the bottom-center pill overlay. |
| `BYNUM_DICTATE_TRAY` | `1` | Enable the tray indicator. |
| `BYNUM_DICTATE_SOUND` | `1` | Enable start/stop/done/error tones. |
| `BYNUM_DICTATE_OVERLAY_RENDER_MS` | `8` | Overlay render loop interval while visible. |
| `BYNUM_DICTATE_OVERLAY_ANIMATION_MS` | `75` | Pill animation duration. |
| `BYNUM_DICTATE_TEXT_RENDER_PYTHON` | `/usr/bin/python3` | Python used for Pillow text rendering. |

## Vocabulary

Put one term per line in:

```bash
~/.config/bynum-dictate/vocabulary.txt
```

Blank lines and `#` comments are ignored. Terms are deduplicated case-insensitively and passed to Faster-Whisper as hotwords plus a short initial prompt.
