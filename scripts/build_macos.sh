#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend audit
python3.12 -m venv .venv-build-macos
. .venv-build-macos/bin/activate
python -m pip install -r requirements.txt
python -m pytest
python -m PyInstaller --clean --noconfirm build_macos.spec --distpath dist --workpath build/pyinstaller-macos
echo "Aplicación lista en dist/RuralFindMe.app"
