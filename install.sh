#!/bin/sh
# kokoro-voice installer. Builds an isolated Python environment in ~/.kokoro and
# puts `speak` and `hush` on your PATH. Nothing here touches system Python.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
K="${KOKORO_HOME:-$HOME/.kokoro}"
BIN="$HOME/.local/bin"

[ "$(uname)" = "Darwin" ] || {
  echo "This needs macOS: it plays audio with afplay and floats the transcript"
  echo "window with Cocoa. Linux would need aplay/paplay and a different window"
  echo "layer - the speech engine itself is portable."; exit 1; }

echo "==> espeak-ng (phoneme fallback for unknown words)"
if command -v espeak-ng >/dev/null 2>&1; then echo "    already present"
elif command -v brew >/dev/null 2>&1; then brew install espeak-ng
else echo "    NOT FOUND and no Homebrew. Install espeak-ng, then re-run."; exit 1
fi

echo "==> Python environment in $K"
mkdir -p "$K"
if [ ! -x "$K/.venv/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then uv venv --python 3.12 "$K/.venv"
  else
    python3 -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info < (3,14) else 1)' || {
      echo "    Need Python 3.10-3.13 (PyTorch has no 3.14 wheels yet)."; exit 1; }
    python3 -m venv "$K/.venv"
  fi
fi

echo "==> dependencies (this pulls PyTorch; a few minutes on a cold cache)"
if command -v uv >/dev/null 2>&1; then
  VIRTUAL_ENV="$K/.venv" uv pip install -q kokoro soundfile pyobjc-framework-Cocoa
else
  "$K/.venv/bin/pip" install -q --upgrade pip
  "$K/.venv/bin/pip" install -q kokoro soundfile pyobjc-framework-Cocoa
fi

# Kokoro's phonemiser needs spaCy's small English model. If it is missing it
# tries to fetch it AT RUNTIME by shelling out to pip/uv - which has no
# virtualenv context inside the daemon and fails with a confusing error. Install
# it now so that never happens.
echo "==> spaCy English model"
SPACY_WHL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
if "$K/.venv/bin/python" -c "import en_core_web_sm" 2>/dev/null; then
  echo "    already present"
elif command -v uv >/dev/null 2>&1; then
  VIRTUAL_ENV="$K/.venv" uv pip install -q "en_core_web_sm @ $SPACY_WHL"
else
  "$K/.venv/bin/pip" install -q "$SPACY_WHL"
fi

"$K/.venv/bin/python" -c "import tkinter" 2>/dev/null || {
  echo "    WARNING: this Python has no tkinter, so the floating transcript"
  echo "    window will not run. Speech still works. Fix: brew install python-tk"; }

echo "==> linking speak and hush into $BIN"
mkdir -p "$BIN"
ln -sf "$HERE/bin/speak" "$BIN/speak"
ln -sf "$HERE/bin/hush"  "$BIN/hush"
case ":$PATH:" in *":$BIN:"*) ;; *)
  echo "    NOTE: $BIN is not on your PATH. Add this to your shell profile:"
  echo "      export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo
echo "Installed. The first thing you speak downloads the model (about 330 MB)."
echo "Try it:   speak \"the machine is awake\""
