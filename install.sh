#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${BYNUM_DICTATE_APP_DIR:-$HOME/.local/share/bynum-dictate}"
BIN_DIR="${BYNUM_DICTATE_BIN_DIR:-$HOME/.local/bin}"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/bynum-dictate-hotkey.desktop"
PYTHON="${PYTHON:-python3}"

mkdir -p "$APP_DIR" "$BIN_DIR" "$AUTOSTART_DIR" "$HOME/.config/bynum-dictate"

if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  install -m 644 "$SRC_DIR"/bynum_dictate*.py "$APP_DIR"/
  install -m 644 "$SRC_DIR"/requirements.txt "$APP_DIR"/
  install -m 644 "$SRC_DIR"/README.md "$APP_DIR"/
  install -m 644 "$SRC_DIR"/bynum-dictate-hotkey.desktop.in "$APP_DIR"/
  install -m 755 "$SRC_DIR"/install.sh "$APP_DIR"/
fi

if [[ ! -d "$APP_DIR/.venv" ]]; then
  "$PYTHON" -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/python" -m ensurepip --upgrade >/dev/null
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip wheel
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

cat >"$BIN_DIR/bynum-dictate" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${BYNUM_DICTATE_APP_DIR:-$HOME/.local/share/bynum-dictate}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "bynum-dictate: virtualenv python not found at $PY" >&2
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
export BYNUM_DICTATE_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/bynum_dictate.py" "$@"
EOF

cat >"$BIN_DIR/bynum-dictate-hotkey" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${BYNUM_DICTATE_APP_DIR:-$HOME/.local/share/bynum-dictate}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "bynum-dictate-hotkey: virtualenv python not found at $PY" >&2
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
export BYNUM_DICTATE_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/bynum_dictate_hotkey.py" "$@"
EOF

cat >"$BIN_DIR/bynum-dictate-once" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${BYNUM_DICTATE_BIN_DIR:-$HOME/.local/bin}"
exec "$BIN_DIR/bynum-dictate" record --paste --notify "$@"
EOF

cat >"$BIN_DIR/bynum-dictate-restart" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${BYNUM_DICTATE_APP_DIR:-$HOME/.local/share/bynum-dictate}"
PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "bynum-dictate-restart: virtualenv python not found at $PY" >&2
  echo "Run $APP_DIR/install.sh first." >&2
  exit 1
fi
export BYNUM_DICTATE_APP_DIR="$APP_DIR"
export PYTHONDONTWRITEBYTECODE=1

exec "$PY" "$APP_DIR/bynum_dictate_restart.py" "$@"
EOF

chmod +x "$BIN_DIR/bynum-dictate" "$BIN_DIR/bynum-dictate-hotkey" "$BIN_DIR/bynum-dictate-once" "$BIN_DIR/bynum-dictate-restart"

if [[ ! -f "$HOME/.config/bynum-dictate/vocabulary.txt" ]]; then
  cat >"$HOME/.config/bynum-dictate/vocabulary.txt" <<'EOF'
# One custom vocabulary term per line.
# Examples:
# CTranslate2
# faster-whisper
# Bynum Dictate
EOF
fi

install -m 644 "$APP_DIR/bynum-dictate-hotkey.desktop.in" "$DESKTOP_FILE"

cat <<EOF
Installed Bynum Dictate.

Commands:
  bynum-dictate warmup --allow-download
  bynum-dictate-hotkey

Autostart:
  $DESKTOP_FILE

Custom vocabulary:
  $HOME/.config/bynum-dictate/vocabulary.txt
EOF
