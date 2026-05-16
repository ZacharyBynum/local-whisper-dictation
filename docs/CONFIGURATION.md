# Configuration

Bynum Dictate is configured with environment variables and one vocabulary file.

## Files

- App directory: `~/.local/share/bynum-dictate`
- Model cache: `~/.local/share/bynum-dictate/models`
- Config directory: `~/.config/bynum-dictate`
- Vocabulary file: `~/.config/bynum-dictate/vocabulary.txt`
- State/log directory: `~/.local/state/bynum-dictate`
- Autostart entry: `~/.config/autostart/bynum-dictate-hotkey.desktop`

These paths can be overridden with `BYNUM_DICTATE_APP_DIR`, `BYNUM_DICTATE_BIN_DIR`, `BYNUM_DICTATE_MODEL_CACHE`, `BYNUM_DICTATE_CONFIG_DIR`, `BYNUM_DICTATE_STATE_DIR`, `BYNUM_DICTATE_VOCABULARY`, and `BYNUM_DICTATE_LOCK_PATH`.

`./install.sh` installs the CPU-oriented runtime by default. Set `BYNUM_DICTATE_INSTALL_CUDA=1` when running the installer to add the NVIDIA CUDA Python wheels from `requirements-cuda.txt`.

## Model Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_MODEL` | `tiny.en` | Faster-Whisper model alias or local path. |
| `BYNUM_DICTATE_DEVICE` | `cpu` | Inference device: `cuda`, `cpu`, or `auto`. |
| `BYNUM_DICTATE_COMPUTE` | `int8` | CTranslate2 compute type. |
| `BYNUM_DICTATE_CPU_FALLBACK` | `1` | Fall back to CPU when CUDA is requested but unavailable. |
| `BYNUM_DICTATE_CPU_MODEL` | `tiny.en` | Model used by CUDA fallback. |
| `BYNUM_DICTATE_CPU_COMPUTE` | `int8` | Compute type used by CUDA fallback. |
| `BYNUM_DICTATE_BEAM_SIZE` | `1` | Beam size. Higher can improve accuracy at a speed cost. |
| `BYNUM_DICTATE_LANGUAGE` | `en` | Language hint. Empty string enables auto-detect. |
| `BYNUM_DICTATE_LOCAL_ONLY` | `1` | Prevent runtime model downloads. |
| `BYNUM_DICTATE_VAD` | `0` | Enable Faster-Whisper VAD filtering. |
| `BYNUM_DICTATE_NO_SPEECH_THRESHOLD` | `0.45` | Whisper no-speech threshold. |
| `BYNUM_DICTATE_PRELOAD` | `1` | Load the hotkey daemon model at startup. |
| `BYNUM_DICTATE_VOCABULARY_MAX_CHARS` | `240` hotkey, `1800` CLI | Maximum custom vocabulary text passed to Faster-Whisper. |

## Hotkey Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_CHORD_GRACE` | `0.70` | Seconds allowed between pressing left Control and left Windows. |
| `BYNUM_DICTATE_MAX_SECONDS` | `45` | Maximum recording duration before auto-stop. |
| `BYNUM_DICTATE_RETRIGGER_COOLDOWN` | `0.30` | Delay before another recording can start. |
| `BYNUM_DICTATE_KEY_POLL_INTERVAL` | `0.08` | Physical key polling interval. |
| `BYNUM_DICTATE_SECONDS` | `8` | Default fixed recording length for `bynum-dictate record`. |
| `BYNUM_DICTATE_BUSY_NOTICE_MS` | `650` | Duration for a normal busy notice. |
| `BYNUM_DICTATE_BUSY_STUCK_SECONDS` | `2.0` | Busy time before showing the longer stuck-state notice. |
| `BYNUM_DICTATE_BUSY_STUCK_NOTICE_MS` | `8000` | Duration for the stuck-state busy notice. |

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
| `BYNUM_DICTATE_START_TONE_BEFORE_RECORD` | `1` | Play the start tone before capture begins. |

## UI Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_OVERLAY` | `1` | Enable the bottom-center pill overlay. |
| `BYNUM_DICTATE_TRAY` | `1` | Enable the tray indicator. |
| `BYNUM_DICTATE_SOUND` | `1` | Enable start/stop/done/error tones. |
| `BYNUM_DICTATE_READY_NOTIFICATION` | `1` | Show a desktop notification when the hotkey daemon is ready. |
| `BYNUM_DICTATE_TRAY_PYTHON` | `/usr/bin/python3` | Python used for the Gtk tray process. |
| `BYNUM_DICTATE_OVERLAY_RENDER_MS` | `8` | Overlay render loop interval while visible. |
| `BYNUM_DICTATE_OVERLAY_IDLE_MS` | `16` | Overlay render interval while idle. |
| `BYNUM_DICTATE_OVERLAY_ANIMATION_MS` | `75` | Pill animation duration. |
| `BYNUM_DICTATE_OVERLAY_ANIMATION_OFFSET` | `10` | Vertical animation travel in pixels. |
| `BYNUM_DICTATE_LEVEL_STARTUP_DAMPEN_MS` | `240` | Initial waveform dampening window after listening starts. |
| `BYNUM_DICTATE_TEXT_RENDER_PYTHON` | `/usr/bin/python3` | Python used for Pillow text rendering. |
| `BYNUM_DICTATE_RESTART_COMMAND` | `~/.local/bin/bynum-dictate-restart` | Command run by the overlay restart control. |

## Visual Level Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_VISUAL_FLOOR` | `0.003` | RMS noise floor for waveform display. |
| `BYNUM_DICTATE_VISUAL_LEVEL_FLOOR` | `0.045` | Minimum displayed waveform level. |
| `BYNUM_DICTATE_VISUAL_CEILING` | `0.90` | Peak level mapped to full visual height. |
| `BYNUM_DICTATE_VISUAL_DB_FLOOR` | `-48` | Lower dB bound for visual scaling. |
| `BYNUM_DICTATE_VISUAL_DB_CEILING` | `-5` | Upper dB bound for visual scaling. |

## Clipboard Settings

| Variable | Default | Description |
| --- | --- | --- |
| `BYNUM_DICTATE_CLIPBOARD_READY_TIMEOUT` | `0.25` | Seconds to wait for a clipboard owner before treating the copy as ready. |

## Vocabulary

Put one term per line in:

```bash
~/.config/bynum-dictate/vocabulary.txt
```

Blank lines and `#` comments are ignored. Terms are deduplicated case-insensitively and passed to Faster-Whisper as hotwords plus a short initial prompt.
