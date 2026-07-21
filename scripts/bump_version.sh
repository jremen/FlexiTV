#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADDON_XML="$ROOT/plugin.video.flexitv/addon.xml"

COMPONENT="patch"
case "${1:-}" in
  ""|--patch) COMPONENT="patch" ;;
  --minor)    COMPONENT="minor" ;;
  --major)    COMPONENT="major" ;;
  -h|--help)
    echo "Usage: $(basename "$0") [--patch|--minor|--major]"
    echo "  Default: --patch  (1.0.0 → 1.0.1)"
    echo "  --minor:          1.0.0 → 1.1.0"
    echo "  --major:          1.0.0 → 2.0.0"
    exit 0
    ;;
  *) echo "usage: $0 [--patch|--minor|--major]" >&2; exit 2 ;;
esac

OLD=$(sed -n '/<addon[^>]* version="\([^"]*\)".*/s//\1/p' "$ADDON_XML" | head -1)

if [ -z "$OLD" ]; then
  echo "Error: could not read version from $ADDON_XML" >&2
  exit 1
fi

IFS='.' read -r MAJ MIN PAT <<< "$OLD"
MAJ=${MAJ:-0}; MIN=${MIN:-0}; PAT=${PAT:-0}

case "$COMPONENT" in
  patch) PAT=$((PAT + 1)) ;;
  minor) MIN=$((MIN + 1)); PAT=0 ;;
  major) MAJ=$((MAJ + 1)); MIN=0; PAT=0 ;;
esac
NEW="$MAJ.$MIN.$PAT"

sed -i '' "/<addon[^>]* version=/s|version=\"$OLD\"|version=\"$NEW\"|" "$ADDON_XML"
echo "Bumped $OLD → $NEW ($COMPONENT)"
