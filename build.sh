#!/bin/bash
set -euo pipefail

ADDON_DIR="plugin.video.flexitv"
ZIP_NAME="${ADDON_DIR}-$(sed -n 's/.*<addon[^>]* version="\([^"]*\)".*/\1/p' "$ADDON_DIR/addon.xml" | head -1).zip"

echo "=== Stripping xattrs ==="
xattr -cr "$ADDON_DIR/" 2>/dev/null || true

echo "=== Ensuring +x on node binary ==="
chmod +x "$ADDON_DIR/resources/lib/python-deps/playwright/driver/node"

if [[ -n "${FLEXI_USER:-}" && -n "${FLEXI_PASS:-}" ]]; then
  echo "=== Fetching channel logos ==="
  python3 scripts/fetch_logos.py --user "$FLEXI_USER" --pass "$FLEXI_PASS" || echo "WARNING: logo fetch failed, continuing"
else
  echo "=== Skipping logo fetch (set FLEXI_USER/FLEXI_PASS to fetch) ==="
fi

echo "=== Building $ZIP_NAME ==="
rm -f "$ZIP_NAME"
zip -r "$ZIP_NAME" "$ADDON_DIR/" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*__pycache__*" \
  -x ".*" \
  -x "*._*" \
  -x "*.DS_Store" \
  -x "$ADDON_DIR/README.md" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/tests/*" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/platform/*" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/platform/**" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/*.cpp" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/*.hpp" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/*.h" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/slp_platformselect.h" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/PyGreenlet.hpp" \
  -x "$ADDON_DIR/resources/lib/python-deps/greenlet/greenlet.h"

echo "=== Done: $(ls -lh "$ZIP_NAME" | awk '{print $5}') ==="
