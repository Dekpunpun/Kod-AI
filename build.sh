#!/usr/bin/env bash
# Build "Kod AI.app" on macOS (or a plain binary on Linux).
# For a Windows .exe you must run build.bat on a Windows machine — PyInstaller
# does not cross-compile.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== installing dependencies ==="
python3 -m pip install --quiet --upgrade -r requirements.txt

echo "=== generating the icon ==="
python3 rpg/make_icon.py

echo "=== building ==="
python3 -m PyInstaller --noconfirm --clean KodAI.spec

echo "=== checking the build actually runs ==="
if [[ "$OSTYPE" == darwin* ]]; then
  BIN="dist/Kod AI.app/Contents/MacOS/KodAI"
else
  BIN="dist/KodAI/KodAI"
fi
"$BIN" --selftest

cat <<'EOF'

============================================================
 Done.
   macOS   dist/Kod AI.app   (double-click it)
   Linux   dist/KodAI/KodAI
 Ship the whole folder/bundle, not just the inner binary.
============================================================
EOF
