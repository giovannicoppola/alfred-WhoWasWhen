#!/bin/bash
# Preflight for a WhoWasWhen release. Run against source/ (or an unpacked
# .alfredworkflow) BEFORE shipping.
#
# Exists because v0.4 shipped `whowaswhen` as a second copy of `ruler-query`.
# The workflow has no database: ruler-query execs its sibling `whowaswhen` to
# build one on first run, so a `whowaswhen` that is really ruler-query execs
# itself without bound. Both binaries are signed under their own name, so
# codesign/spctl pass and the mistake is invisible.
#
# Do NOT identify the builder by "database created successfully" — ruler-query
# also embeds that literal, in the guard that checks the child's output.

set -u
DIR="${1:-source}"
fail=0
note() { printf '  %-34s %s\n' "$1" "$2"; }

for b in ruler-query whowaswhen; do
	[ -f "$DIR/$b" ] || { echo "MISSING: $DIR/$b"; fail=1; continue; }
done
[ "$fail" = 1 ] && exit 1

echo "Checking $DIR"

# 1. The two binaries must be different programs.
if [ "$(md5 -q "$DIR/ruler-query")" = "$(md5 -q "$DIR/whowaswhen")" ]; then
	note "distinct binaries" "FAIL (identical files)"; fail=1
else
	note "distinct binaries" "ok"
fi

# 2. whowaswhen must be the DB generator, ruler-query must not be.
if strings -a "$DIR/whowaswhen" | grep -q "Fetching data from public Google Sheets"; then
	note "whowaswhen is the DB builder" "ok"
else
	note "whowaswhen is the DB builder" "FAIL (it is not the generator)"; fail=1
fi
if strings -a "$DIR/ruler-query" | grep -q "Fetching data from public Google Sheets"; then
	note "ruler-query is the querier" "FAIL (it is the generator)"; fail=1
else
	note "ruler-query is the querier" "ok"
fi

# 3. The builder must emit the born/died columns the querier selects.
if strings -a "$DIR/whowaswhen" | grep -q "biography, born, died"; then
	note "builder writes born/died" "ok"
else
	note "builder writes born/died" "FAIL (stale builder; r.born will not exist)"; fail=1
fi

# 4. The querier must carry the exec-recursion guard.
if strings -a "$DIR/ruler-query" | grep -q "WHOWASWHEN_UPDATE_CHILD"; then
	note "recursion guard present" "ok"
else
	note "recursion guard present" "FAIL (a mis-packaged build could fork bomb)"; fail=1
fi

# 5. Gatekeeper: a downloaded .alfredworkflow is quarantined.
for b in ruler-query whowaswhen; do
	if spctl -a -t install "$DIR/$b" >/dev/null 2>&1; then
		note "$b signed + notarized" "ok"
	else
		note "$b signed + notarized" "FAIL (would be blocked on download)"; fail=1
	fi
done

[ "$fail" = 0 ] && echo "PASS" || echo "FAILED — do not ship"
exit $fail
