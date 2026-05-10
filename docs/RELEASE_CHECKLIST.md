# Release Checklist

Use this before tagging a release.

## Local Checks

```bash
make check
```

## Manual Desktop Checks

- Start `bynum-dictate-hotkey`.
- Confirm tray icon appears.
- Hold left Control + left Windows and verify the overlay appears.
- Speak a short sentence and confirm it pastes into a normal text field.
- Speak into a terminal and confirm paste uses `Ctrl+Shift+V`.
- Click/release without speech and confirm no hallucinated text is pasted.
- Trigger a stuck/error state and verify the overlay restart control asks for confirmation.

## Privacy Checks

- Confirm `BYNUM_DICTATE_LOCAL_ONLY=1` by default.
- Confirm model download requires `--allow-download` or `BYNUM_DICTATE_LOCAL_ONLY=0`.
- Confirm no telemetry, cloud transcription, or transcript upload was added.

## Repository Checks

- Confirm `.venv/`, `models/`, caches, logs, and generated audio are untracked.
- Confirm README install steps match the current scripts.
- Confirm CI is green on supported Python versions.
- Confirm changelog is updated.
