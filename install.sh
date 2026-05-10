#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${LOCAL_WHISPER_APP_DIR:-$HOME/.local/share/local-whisper}"
BIN_DIR="${LOCAL_WHISPER_BIN_DIR:-$HOME/.local/bin}"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/local-whisper-hotkey.desktop"
PYTHON="${PYTHON:-python3}"

mkdir -p "$APP_DIR" "$BIN_DIR" "$AUTOSTART_DIR" "$HOME/.config/local-whisper"

if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  install -m 644 "$SRC_DIR"/local_whisper*.py "$APP_DIR"/
  install -m 644 "$SRC_DIR"/requirements.txt "$APP_DIR"/
  install -m 644 "$SRC_DIR"/README.md "$APP_DIR"/
  install -m 644 "$SRC_DIR"/local-whisper-hotkey.desktop.in "$APP_DIR"/
  install -m 755 "$SRC_DIR"/install.sh "$APP_DIR"/
fi

if [[ ! -d "$APP_DIR/.venv" ]]; then
  "$PYTHON" -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/python" -m ensurepip --upgrade >/dev/null
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip wheel
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

cat >"$BIN_DIR/local-whisper" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LOCAL_WHISPER_APP_DIR:-$HOME/.local/share/local-whisper}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "local-whisper: virtualenv python not found at $PY" >&2
  echo "Run $APP_DIR/install.sh first." >&2
  exit 1
fi
PYVER="$("$PY" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
NVIDIA_LIB="$APP_DIR/.venv/lib/python$PYVER/site-packages/nvidia"
export LD_LIBRARY_PATH="$NVIDIA_LIB/cublas/lib:$NVIDIA_LIB/cudnn/lib:${LD_LIBRARY_PATH:-}"
export LOCAL_WHISPER_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/local_whisper.py" "$@"
EOF

cat >"$BIN_DIR/local-whisper-hotkey" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LOCAL_WHISPER_APP_DIR:-$HOME/.local/share/local-whisper}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "local-whisper-hotkey: virtualenv python not found at $PY" >&2
  echo "Run $APP_DIR/install.sh first." >&2
  exit 1
fi
PYVER="$("$PY" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
NVIDIA_LIB="$APP_DIR/.venv/lib/python$PYVER/site-packages/nvidia"
export LD_LIBRARY_PATH="$NVIDIA_LIB/cublas/lib:$NVIDIA_LIB/cudnn/lib:${LD_LIBRARY_PATH:-}"
export LOCAL_WHISPER_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/local_whisper_hotkey.py" "$@"
EOF

cat >"$BIN_DIR/local-whisper-dictate" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${LOCAL_WHISPER_BIN_DIR:-$HOME/.local/bin}"
exec "$BIN_DIR/local-whisper" record --paste --notify "$@"
EOF

cat >"$BIN_DIR/local-whisper-restart" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LOCAL_WHISPER_APP_DIR:-$HOME/.local/share/local-whisper}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "local-whisper-restart: virtualenv python not found at $PY" >&2
  echo "Run $APP_DIR/install.sh first." >&2
  exit 1
fi
export LOCAL_WHISPER_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/local_whisper_restart.py" "$@"
EOF

chmod +x "$BIN_DIR/local-whisper" "$BIN_DIR/local-whisper-hotkey" "$BIN_DIR/local-whisper-dictate" "$BIN_DIR/local-whisper-restart"

if [[ ! -f "$HOME/.config/local-whisper/vocabulary.txt" ]]; then
  cat >"$HOME/.config/local-whisper/vocabulary.txt" <<'EOF'
# One custom vocabulary term per line.
# Examples:
# CTranslate2
# faster-whisper
# Local Whisper
EOF
fi

install -m 644 "$APP_DIR/local-whisper-hotkey.desktop.in" "$DESKTOP_FILE"

cat <<EOF
Installed Local Whisper.

Commands:
  local-whisper warmup --allow-download
  local-whisper-hotkey

Autostart:
  $DESKTOP_FILE

Custom vocabulary:
  $HOME/.config/local-whisper/vocabulary.txt
EOF
