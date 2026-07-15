#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Este script debe ejecutarse en macOS." >&2
  exit 1
fi

SOURCE="$ROOT/dist/RuralFindMe.app"
if [[ ! -d "$SOURCE" ]]; then
  echo "No se encontró dist/RuralFindMe.app. Ejecute scripts/build_macos.sh primero." >&2
  exit 1
fi

VERSION="$(python3 -c 'from app import __version__; print(__version__)')"
DESTINATION="$ROOT/dist/RuralFindMe-${VERSION}-macOS.zip"

# An ad-hoc signature preserves bundle integrity for private sharing. Public,
# warning-free distribution still requires Developer ID signing and notarization.
codesign --force --deep --sign - "$SOURCE"
codesign --verify --deep --strict "$SOURCE"

ditto -c -k --sequesterRsrc --keepParent "$SOURCE" "$DESTINATION"
unzip -tq "$DESTINATION"

echo "Paquete macOS listo en: $DESTINATION"
echo "Nota: para distribución pública, firme con Developer ID y notarice con Apple."
