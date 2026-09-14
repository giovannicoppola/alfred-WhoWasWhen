#!/bin/bash
# Package a WhoWasWhen .alfredworkflow.
#
# The workflow folder Alfred runs is a SYMLINK to this repo's source/:
#   ~/…/Alfred.alfredpreferences/workflows/giovanni-whowaswhen -> source
# so source/ is the live workflow. ruler-query consumes whoWasWhen.zip on first
# run and deletes it, which means a zip left sitting in source/ is destroyed by
# the next local query. The archive is therefore built here, at package time,
# into a staging copy — never into source/.
#
# Usage: pkg/package-release.sh <version> [path/to/whoWasWhen.db]

set -euo pipefail

VERSION="${1:?usage: package-release.sh <version> [db-path]}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$HOME/Library/Application Support/Alfred/Workflow Data/giovanni-whowaswhen"
DB="${2:-$DATA_DIR/whoWasWhen.db}"
STAMP="$DATA_DIR/timestamp.txt"
OUT="$REPO/releases/WhoWhasWhen_${VERSION}.alfredworkflow"

[ -f "$DB" ] || { echo "No database at $DB — run source/whowaswhen -alfred first"; exit 1; }

stage=$(mktemp -d); trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/bundle" "$stage/db"

# The database the release ships, plus the date it was generated. Shipping the
# timestamp keeps the refresh cycle honest: someone installing an old release
# refreshes on schedule instead of getting a fresh CHECK_RATE window.
cp "$DB" "$stage/db/whoWasWhen.db"
if [ -f "$STAMP" ]; then
	cp "$STAMP" "$stage/db/timestamp.txt"
else
	date '+%Y-%m-%d %H:%M:%S' > "$stage/db/timestamp.txt"
fi
( cd "$stage/db" && zip -X -q -9 "$stage/bundle/whoWasWhen.zip" whoWasWhen.db timestamp.txt )

# Workflow files. prefs.plist is this machine's own settings, not shippable.
( cd "$REPO/source" && tar -cf - \
	--exclude prefs.plist --exclude .DS_Store --exclude whoWasWhen.zip . ) \
	| ( cd "$stage/bundle" && tar -xf - )

rm -f "$OUT"
( cd "$stage/bundle" && zip -r -X -q "$OUT" . )

echo "Built $OUT ($(du -h "$OUT" | cut -f1))"
echo

# Verify what actually shipped, not what is sitting in source/.
check=$(mktemp -d); trap 'rm -rf "$stage" "$check"' EXIT
unzip -qo "$OUT" -d "$check"
"$REPO/pkg/verify-release.sh" "$check"
